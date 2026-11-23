"""Dialogue de publication d'une ressource dans le catalogue CampusShare."""
import asyncio
import logging
import mimetypes
from pathlib import Path

import flet as ft
import theme
from compat import notify, pad_all
from core.p2p import build_manifest
from services.backend_client import BackendApiError

logger = logging.getLogger(__name__)

CATEGORIES = [
    ("COURSE", "Cours (CM)"),
    ("EXERCISE", "TD / TP"),
    ("EXAM", "Examen"),
    ("PROJECT", "Projet"),
    ("MEDIA", "Média / Enregistrement"),
]


async def open_publish_dialog(page: ft.Page, backend_client=None, sharing_service=None):
    if backend_client is None or not backend_client.is_authenticated:
        notify(page, "Connectez-vous au serveur avant de publier une ressource.", "warning")
        return

    selected_path = {"value": ""}

    title_field = ft.TextField(label="Titre", width=420)
    description_field = ft.TextField(label="Description", multiline=True, min_lines=2, max_lines=4, width=420)
    course_field = ft.TextField(label="Code UE / cours", hint_text="ex: INF101", width=200)
    category_field = ft.Dropdown(
        label="Catégorie",
        width=200,
        value="COURSE",
        options=[ft.dropdown.Option(key=k, text=v) for k, v in CATEGORIES] if hasattr(ft, "dropdown") else None,
    )
    # Compat: some Flet versions use Dropdown(options=[ft.DropdownOption(...)])
    if not getattr(category_field, "options", None):
        try:
            category_field.options = [ft.DropdownOption(key=k, text=v) for k, v in CATEGORIES]
        except Exception:
            category_field.options = [ft.DropdownOption(v) for _, v in CATEGORIES]

    path_field = ft.TextField(label="Chemin du fichier (local)", width=420, read_only=False)
    status_text = ft.Text("", size=12, color=theme.TEXT_MUTED)

    async def do_pick(_e):
        try:
            picker = ft.FilePicker()
            if picker not in page.overlay:
                page.overlay.append(picker)
                page.update()
            if hasattr(picker, "pick_files_async"):
                files = await picker.pick_files_async(allow_multiple=False)
            elif hasattr(picker, "pick_files"):
                # callback style fallback: not easy in async flow; ask for path
                notify(page, "Sélection automatique non disponible ici, saisissez le chemin du fichier.", "info")
                return
            else:
                notify(page, "Sélecteur indisponible, saisissez le chemin du fichier.", "info")
                return
            if files:
                file = files[0]
                path = getattr(file, "path", None) or getattr(file, "name", "")
                if path:
                    selected_path["value"] = path
                    path_field.value = path
                    if not title_field.value:
                        title_field.value = Path(path).stem
                    page.update()
        except Exception as exc:
            logger.exception("Sélection de fichier impossible")
            notify(page, f"Sélection indisponible : {exc}. Saisissez le chemin.", "warning")

    async def do_publish(_e):
        path_value = (path_field.value or selected_path["value"] or "").strip().strip('"')
        if not path_value:
            notify(page, "Indiquez un fichier à publier.", "error")
            return
        file_path = Path(path_value)
        if not file_path.exists() or not file_path.is_file():
            notify(page, "Le fichier indiqué est introuvable.", "error")
            return
        title = (title_field.value or "").strip() or file_path.stem
        course_code = (course_field.value or "").strip() or "GEN"
        category = getattr(category_field, "value", None) or "COURSE"
        description = (description_field.value or "").strip()
        publish_button.disabled = True
        status_text.value = "Calcul du manifeste SHA-256..."
        status_text.color = theme.TEXT_MUTED
        page.update()
        try:
            manifest = await asyncio.to_thread(build_manifest, file_path)
            mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            payload = {
                "title": title,
                "description": description,
                "course_code": course_code,
                "category": category,
                "file_name": file_path.name,
                "file_size": manifest.file_size,
                "mime_type": mime_type,
                "piece_size": manifest.piece_size,
                "piece_count": manifest.piece_count,
                "root_hash": manifest.root_hash,
                "manifest": list(manifest.piece_hashes),
            }
            status_text.value = "Publication dans le catalogue..."
            page.update()
            created = await backend_client.create_resource(payload)
            status_text.value = "Ressource publiée dans le catalogue."
            status_text.color = theme.SUCCESS
            notify(page, "Ressource publiée dans le catalogue.", "success")
            # Option: partager immédiatement ce fichier comme seeder si possible.
            if sharing_service is not None and isinstance(created, dict) and created.get("id"):
                resource = {
                    "id": created.get("id"),
                    "file_name": payload["file_name"],
                    "file_size": payload["file_size"],
                    "piece_size": payload["piece_size"],
                    "piece_count": payload["piece_count"],
                    "root_hash": payload["root_hash"],
                    "manifest": payload["manifest"],
                }
                try:
                    await sharing_service.share_resource(resource, str(file_path), remember=True)
                    notify(page, "Ressource partagée sur le réseau local.", "success")
                except Exception as exc:
                    logger.exception("Partage automatique après publication impossible")
                    notify(page, f"Publiée, mais partage local impossible : {exc}", "warning")
            dialog.open = False
            page.update()
        except (BackendApiError, OSError, ValueError, TypeError, KeyError) as exc:
            logger.exception("Publication impossible")
            status_text.value = f"Publication impossible : {exc}"
            status_text.color = theme.ERROR
            notify(page, f"Publication impossible : {exc}", "error")
            page.update()
        finally:
            publish_button.disabled = False
            try:
                page.update()
            except Exception:
                pass

    pick_button = ft.OutlinedButton("Choisir un fichier", icon=ft.Icons.FOLDER_OPEN, on_click=lambda e: page.run_task(do_pick, e) if hasattr(page, "run_task") else None)
    publish_button = ft.Button("Publier", icon=ft.Icons.CLOUD_UPLOAD, on_click=lambda e: page.run_task(do_publish, e) if hasattr(page, "run_task") else None)

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Publier une ressource"),
        content=ft.Container(
            width=460,
            padding=pad_all(4),
            content=ft.Column(
                tight=True,
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text("Ajoute les métadonnées et le manifeste SHA-256 au catalogue (le fichier n'est pas téléversé au serveur).", size=12, color=theme.TEXT_MUTED),
                    title_field,
                    description_field,
                    ft.Row(controls=[course_field, category_field]),
                    ft.Row(controls=[path_field]),
                    pick_button,
                    status_text,
                ],
            ),
        ),
        actions=[
            ft.TextButton("Annuler", on_click=lambda e: setattr(dialog, "open", False) or page.update()),
            publish_button,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def close_cancel(_e):
        dialog.open = False
        page.update()

    dialog.actions[0].on_click = close_cancel
    page.open(dialog)
