import base64
import binascii
import hashlib
import re

from django.shortcuts import get_object_or_404
from rest_framework import serializers

from apps.network_registry.models import PeerNodeIdentity

from .models import AcademicResource, FileSeeder


class AcademicResourceSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.ReadOnlyField(source="uploaded_by.username")
    seeders = serializers.IntegerField(source="online_seeders", read_only=True, default=0)

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
            "seeders",
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


class FileSeederSerializer(serializers.ModelSerializer):
    node_id = serializers.UUIDField(source="node.id", read_only=True)
    lan_ip = serializers.IPAddressField(source="node.lan_ip", read_only=True)
    tcp_port = serializers.IntegerField(source="node.tcp_port", read_only=True)
    node_name = serializers.CharField(source="node.node_name", read_only=True)

    class Meta:
        model = FileSeeder
        fields = (
            "node_id",
            "node_name",
            "lan_ip",
            "tcp_port",
            "availability",
            "bitfield",
            "pieces_available",
            "last_announced",
        )


class SeederAnnounceSerializer(serializers.Serializer):
    resource_id = serializers.UUIDField()
    node_id = serializers.UUIDField()
    bitfield = serializers.CharField()
    pieces_available = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        request = self.context["request"]
        resource = get_object_or_404(
            AcademicResource,
            id=attrs["resource_id"],
            is_published=True,
        )
        node = get_object_or_404(
            PeerNodeIdentity,
            id=attrs["node_id"],
            user=request.user,
        )

        try:
            bitfield = base64.b64decode(attrs["bitfield"], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise serializers.ValidationError(
                {"bitfield": "Le bitfield doit être encodé en base64 valide."}
            ) from exc

        expected_length = (resource.piece_count + 7) // 8
        if len(bitfield) != expected_length:
            raise serializers.ValidationError(
                {"bitfield": "La taille du bitfield ne correspond pas au manifeste."}
            )
        if resource.piece_count % 8 and bitfield:
            unused_mask = 0xFF << (resource.piece_count % 8) & 0xFF
            if bitfield[-1] & unused_mask:
                raise serializers.ValidationError(
                    {"bitfield": "Le bitfield contient des blocs hors manifeste."}
                )
        actual_count = sum(byte.bit_count() for byte in bitfield)
        if attrs["pieces_available"] != actual_count:
            raise serializers.ValidationError(
                {"pieces_available": "Le nombre annoncé ne correspond pas au bitfield."}
            )

        attrs["resource"] = resource
        attrs["node"] = node
        attrs["availability"] = (
            FileSeeder.Availability.FULL
            if actual_count == resource.piece_count
            else FileSeeder.Availability.PARTIAL
        )
        return attrs

    def create(self, validated_data):
        resource = validated_data.pop("resource")
        node = validated_data.pop("node")
        seeder, _ = FileSeeder.objects.update_or_create(
            resource=resource,
            node=node,
            defaults=validated_data,
        )
        return seeder
