import hashlib
import base64

from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.network_registry.models import PeerNodeIdentity

from .models import AcademicResource, FileSeeder


class ResourceApiTests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher",
            password="StrongCampusPass123!",
            role=User.Role.TEACHER,
        )
        self.student = User.objects.create_user(
            username="student",
            password="StrongCampusPass123!",
        )
        self.admin = User.objects.create_user(
            username="admin",
            password="StrongCampusPass123!",
            role=User.Role.ADMIN,
        )
        self.list_url = reverse("resource-list")
        self.block_hashes = [
            hashlib.sha256(b"block one").hexdigest(),
            hashlib.sha256(b"block two").hexdigest(),
        ]
        self.root_hash = hashlib.sha256(
            b"".join(bytes.fromhex(digest) for digest in self.block_hashes)
        ).hexdigest()
        self.payload = {
            "title": "Introduction à Django",
            "description": "Notes de cours",
            "course_code": "INF101",
            "category": AcademicResource.Category.COURSE,
            "file_name": "django.pdf",
            "file_size": 300000,
            "mime_type": "application/pdf",
            "piece_size": 262144,
            "piece_count": 2,
            "root_hash": self.root_hash,
            "manifest": self.block_hashes,
        }

    def create_resource(self, **overrides):
        data = {**self.payload, **overrides}
        return AcademicResource.objects.create(
            **data,
            uploaded_by=self.teacher,
        )

    def test_teacher_can_publish_resource_without_uploading_file_to_server(self):
        self.client.force_authenticate(self.teacher)

        response = self.client.post(self.list_url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        resource = AcademicResource.objects.get(title=self.payload["title"])
        self.assertEqual(resource.uploaded_by, self.teacher)
        self.assertEqual(response.data["uploaded_by"], self.teacher.username)

    def test_student_cannot_publish_resource(self):
        self.client.force_authenticate(self.student)

        response = self.client.post(self.list_url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(AcademicResource.objects.exists())

    def test_catalogue_requires_authentication(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_publication_rejects_a_manifest_with_wrong_root_hash(self):
        self.client.force_authenticate(self.teacher)
        payload = {**self.payload, "root_hash": "0" * 64}

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("root_hash", response.data)

    def test_publication_rejects_piece_count_inconsistent_with_file_size(self):
        self.client.force_authenticate(self.teacher)
        payload = {**self.payload, "piece_count": 1}

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("piece_count", response.data)

    def test_catalogue_search_filters_by_course_category_and_text(self):
        self.create_resource()
        self.create_resource(
            title="Algèbre",
            course_code="MAT202",
            category=AcademicResource.Category.EXAM,
            file_name="algebre.pdf",
            root_hash=hashlib.sha256(
                bytes.fromhex(hashlib.sha256(b"other block").hexdigest())
            ).hexdigest(),
            manifest=[hashlib.sha256(b"other block").hexdigest()],
            file_size=100,
            piece_size=262144,
            piece_count=1,
        )
        self.client.force_authenticate(self.student)

        response = self.client.get(
            self.list_url,
            {"course_code": "INF101", "category": "COURSE", "q": "Django"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Introduction à Django")

    def test_students_cannot_see_unpublished_resources(self):
        resource = self.create_resource(is_published=False)
        self.client.force_authenticate(self.student)

        list_response = self.client.get(self.list_url)
        detail_response = self.client.get(
            reverse("resource-detail", args=[resource.id])
        )

        self.assertEqual(list_response.data["count"], 0)
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_resource_owner_can_update_but_other_student_cannot(self):
        resource = self.create_resource()
        detail_url = reverse("resource-detail", args=[resource.id])

        self.client.force_authenticate(self.student)
        forbidden_response = self.client.patch(
            detail_url,
            {"title": "Titre modifié"},
            format="json",
        )
        self.assertEqual(forbidden_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.teacher)
        update_response = self.client.patch(
            detail_url,
            {"title": "Titre modifié"},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["title"], "Titre modifié")

    def test_administrator_can_remove_another_publishers_resource(self):
        resource = self.create_resource()
        self.client.force_authenticate(self.admin)

        response = self.client.delete(
            reverse("resource-detail", args=[resource.id])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AcademicResource.objects.filter(id=resource.id).exists())

    def test_manifest_endpoint_returns_only_manifest_metadata(self):
        resource = self.create_resource()
        self.client.force_authenticate(self.student)

        response = self.client.get(
            reverse("resource-manifest", args=[resource.id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["manifest"], self.block_hashes)
        self.assertEqual(response.data["root_hash"], self.root_hash)

    def create_node(self, user=None, node_name="laptop"):
        return PeerNodeIdentity.objects.create(
            user=user or self.student,
            node_name=node_name,
            public_key="a" * 64,
            lan_ip="192.168.1.25" if node_name == "laptop" else "192.168.1.26",
            tcp_port=8765,
            platform=PeerNodeIdentity.Platform.DESKTOP,
            is_online=True,
            last_seen=timezone.now(),
        )

    def test_owner_can_announce_seeded_pieces_and_clients_can_list_them(self):
        resource = self.create_resource()
        node = self.create_node()
        self.client.force_authenticate(self.student)
        announce_response = self.client.post(
            reverse("seeder-announce"),
            {
                "resource_id": str(resource.id),
                "node_id": str(node.id),
                "bitfield": base64.b64encode(b"\x03").decode("ascii"),
                "pieces_available": 2,
            },
            format="json",
        )

        self.assertEqual(announce_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            announce_response.data["availability"],
            FileSeeder.Availability.FULL,
        )

        self.client.force_authenticate(self.teacher)
        list_response = self.client.get(
            reverse("resource-seeders", args=[resource.id])
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["results"][0]["lan_ip"], "192.168.1.25")
        self.assertNotIn("public_key", list_response.data["results"][0])

    def test_catalogue_includes_count_of_online_seeders(self):
        resource = self.create_resource()
        node = self.create_node()
        FileSeeder.objects.create(
            resource=resource,
            node=node,
            availability=FileSeeder.Availability.FULL,
            bitfield=base64.b64encode(b"\x03").decode("ascii"),
            pieces_available=2,
        )
        self.client.force_authenticate(self.student)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["seeders"], 1)

    def test_seed_announcement_rejects_node_owned_by_another_user(self):
        resource = self.create_resource()
        node = self.create_node(user=self.teacher)
        self.client.force_authenticate(self.student)

        response = self.client.post(
            reverse("seeder-announce"),
            {
                "resource_id": str(resource.id),
                "node_id": str(node.id),
                "bitfield": base64.b64encode(b"\x03").decode("ascii"),
                "pieces_available": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_seed_announcement_rejects_mismatched_bitfield_count(self):
        resource = self.create_resource()
        node = self.create_node()
        self.client.force_authenticate(self.student)

        response = self.client.post(
            reverse("seeder-announce"),
            {
                "resource_id": str(resource.id),
                "node_id": str(node.id),
                "bitfield": base64.b64encode(b"\x01").decode("ascii"),
                "pieces_available": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pieces_available", response.data)
