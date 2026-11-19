import hashlib
import re

from rest_framework import serializers

from .models import AcademicResource


class AcademicResourceSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.ReadOnlyField(source="uploaded_by.username")

    class Meta:
        model = AcademicResource
        fields = (
            "id",
            "title",
            "description",
            "course_code",
            "category",
            "file_name",
            "file_size",
            "mime_type",
            "piece_size",
            "piece_count",
            "root_hash",
            "manifest",
            "uploaded_by",
            "is_published",
            "created_at",
        )
        read_only_fields = ("id", "uploaded_by", "created_at")

    def validate_manifest(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Le manifeste doit être une liste.")
        if any(
            not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            for digest in value
        ):
            raise serializers.ValidationError(
                "Chaque empreinte de bloc doit être un SHA-256 hexadécimal minuscule."
            )
        return value

    def validate(self, attrs):
        instance = self.instance
        file_size = attrs.get("file_size", getattr(instance, "file_size", None))
        piece_size = attrs.get("piece_size", getattr(instance, "piece_size", 262144))
        piece_count = attrs.get(
            "piece_count",
            getattr(instance, "piece_count", None),
        )
        root_hash = attrs.get("root_hash", getattr(instance, "root_hash", None))
        manifest = attrs.get("manifest", getattr(instance, "manifest", None))

        errors = {}
        if file_size is not None and file_size < 1:
            errors["file_size"] = "La taille du fichier doit être supérieure à zéro."
        if piece_size < 1:
            errors["piece_size"] = "La taille d'un bloc doit être supérieure à zéro."
        if file_size is not None and piece_size > 0 and piece_count is not None:
            expected_count = (file_size + piece_size - 1) // piece_size
            if piece_count != expected_count:
                errors["piece_count"] = (
                    "Le nombre de blocs ne correspond pas à la taille du fichier."
                )
        if manifest is not None and piece_count is not None:
            if len(manifest) != piece_count:
                errors["manifest"] = "Le manifeste doit contenir une empreinte par bloc."
            elif root_hash is not None:
                calculated_root = hashlib.sha256(
                    b"".join(bytes.fromhex(digest) for digest in manifest)
                ).hexdigest()
                if calculated_root != root_hash:
                    errors["root_hash"] = (
                        "L'empreinte racine ne correspond pas au manifeste."
                    )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class ResourceManifestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicResource
        fields = ("id", "piece_size", "piece_count", "root_hash", "manifest")
