# Packaging CampusShare (client desktop)

## Pré-requis

- Python 3.10+ (même majeure/mineure que la cible recommandée)
- Dépendances client installées: `python -m pip install -r requirements.txt`
- Pour WebRTC média optionnel: `python -m pip install -r requirements-webrtc.txt` (sur machine cible compatible)
- Pour PyInstaller: `python -m pip install pyinstaller`
- Pour `flet build windows`: Flet 1.x + Flutter SDK + Visual Studio Build Tools selon la doc Flet

## Build Windows (PyInstaller)

Depuis la racine du dépôt:

```powershell
.\scripts\package_client_windows.ps1 -Mode pyinstaller
```

Sortie: `dist\CampusShare\CampusShare.exe`

## Build Windows (Flet)

```powershell
.\scripts\package_client_windows.ps1 -Mode flet
```

Sortie: `dist\flet-windows\`

## Validation cible

Le packaging doit être validé sur les machines cibles (Windows, permissions caméra/micro/capture écran, même réseau LAN/Wi-Fi, backend accessible). Ce dépôt fournit les scripts/spec; la validation binaire finale dépend de l'environnement cible.
