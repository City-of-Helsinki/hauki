import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_list_resources_empty(admin_client):
    url = reverse("resource-list")

    response = admin_client.get(url)

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 0


@pytest.mark.django_db
def test_list_resources_one_resource(admin_client, resource_factory):
    resource = resource_factory()

    url = reverse("resource-list")

    response = admin_client.get(url)

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == resource.id


@pytest.mark.django_db
def test_list_resources_multiple_resources(admin_client, resource_factory):
    resource = resource_factory()
    resource2 = resource_factory()

    url = reverse("resource-list")

    response = admin_client.get(url)

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 2

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource.id, resource2.id}


@pytest.mark.django_db
def test_list_resources_data_source_filter_none_of_two_match(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()

    resource_factory()
    resource_factory()

    url = reverse("resource-list")

    response = admin_client.get(url, data={"data_source": data_source.id})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 0


@pytest.mark.django_db
def test_list_resources_data_source_filter_one_of_two_match(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source)

    resource_factory()

    url = reverse("resource-list")

    response = admin_client.get(url, data={"data_source": data_source.id})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 1

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource.id}


@pytest.mark.django_db
def test_list_resources_data_source_filter_two_of_two_match(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory()
    resource_origin_factory(resource=resource2, data_source=data_source)

    url = reverse("resource-list")

    response = admin_client.get(url, data={"data_source": data_source.id})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 2

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource.id, resource2.id}


@pytest.mark.django_db
def test_list_resources_origin_id_exists_filter_false_all_match(
    admin_client, resource_factory
):
    resource = resource_factory()
    resource2 = resource_factory()

    url = reverse("resource-list")

    response = admin_client.get(url, data={"origin_id_exists": False})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 2

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource.id, resource2.id}


@pytest.mark.django_db
def test_list_resources_origin_id_exists_filter_false_one_matches(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()

    resource = resource_factory()
    resource2 = resource_factory()
    resource_origin_factory(resource=resource2, data_source=data_source)

    url = reverse("resource-list")

    response = admin_client.get(url, data={"origin_id_exists": False})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 1

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource.id}


@pytest.mark.django_db
def test_list_resources_origin_id_exists_filter_false_none_match(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source)
    resource2 = resource_factory()
    resource_origin_factory(resource=resource2, data_source=data_source)

    url = reverse("resource-list")

    response = admin_client.get(url, data={"origin_id_exists": False})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 0


@pytest.mark.django_db
def test_list_resources_origin_id_exists_filter_true_all_match(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source)
    resource2 = resource_factory()
    resource_origin_factory(resource=resource2, data_source=data_source)

    url = reverse("resource-list")

    response = admin_client.get(url, data={"origin_id_exists": True})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 2

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource.id, resource2.id}


@pytest.mark.django_db
def test_list_resources_origin_id_exists_filter_true_one_matches(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()

    resource_factory()
    resource2 = resource_factory()
    resource_origin_factory(resource=resource2, data_source=data_source)

    url = reverse("resource-list")

    response = admin_client.get(url, data={"origin_id_exists": True})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 1

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource2.id}


@pytest.mark.django_db
def test_list_resources_origin_id_exists_filter_true_none_match(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source_factory()

    resource_factory()
    resource_factory()

    url = reverse("resource-list")

    response = admin_client.get(url, data={"origin_id_exists": True})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 0


@pytest.mark.django_db
def test_list_resources_data_source_and_origin_id_exists_filter_none_match(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    data_source2 = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source)
    resource2 = resource_factory()
    resource_origin_factory(resource=resource2, data_source=data_source)

    url = reverse("resource-list")

    response = admin_client.get(
        url, data={"data_source": data_source2.id, "origin_id_exists": True}
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 0


@pytest.mark.django_db
def test_list_resources_data_source_and_origin_id_exists_filter_all_match(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source)
    resource2 = resource_factory()
    resource_origin_factory(resource=resource2, data_source=data_source)

    url = reverse("resource-list")

    response = admin_client.get(
        url, data={"data_source": data_source.id, "origin_id_exists": True}
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 2

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource.id, resource2.id}


@pytest.mark.django_db
def test_data_source_and_origin_id_exists_two_data_sources(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    data_source2 = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source)
    resource_origin_factory(resource=resource, data_source=data_source2)

    resource2 = resource_factory()
    resource_origin_factory(resource=resource2, data_source=data_source)
    resource_origin_factory(resource=resource2, data_source=data_source2)

    url = reverse("resource-list")

    response = admin_client.get(
        url, data={"data_source": data_source.id, "origin_id_exists": True}
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 2

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource.id, resource2.id}


@pytest.mark.django_db
def test_data_source_and_origin_id_exists_two_data_sources_on_other(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    data_source2 = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source2)

    resource2 = resource_factory()
    resource_origin_factory(resource=resource2, data_source=data_source)
    resource_origin_factory(resource=resource2, data_source=data_source2)

    url = reverse("resource-list")

    response = admin_client.get(
        url, data={"data_source": data_source.id, "origin_id_exists": True}
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 1

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource2.id}


@pytest.mark.django_db
def test_data_source_and_origin_id_exists_false_two_data_sources_on_other(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    data_source2 = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source2)

    resource2 = resource_factory()
    resource_origin_factory(resource=resource2, data_source=data_source)
    resource_origin_factory(resource=resource2, data_source=data_source2)

    url = reverse("resource-list")

    response = admin_client.get(
        url, data={"data_source": data_source.id, "origin_id_exists": False}
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 0


@pytest.mark.django_db
def test_data_source_and_origin_id_exists_false_data_sources_in_parent(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    data_source2 = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source)
    resource_origin_factory(resource=resource, data_source=data_source2)

    resource2 = resource_factory()
    resource.children.add(resource2)

    url = reverse("resource-list")

    response = admin_client.get(
        url, data={"data_source": data_source.id, "origin_id_exists": False}
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 1

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource2.id}


@pytest.mark.django_db
def test_data_source_and_origin_id_exists_false_different_data_source_in_child(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    data_source2 = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source)
    resource_origin_factory(resource=resource, data_source=data_source2)

    resource2 = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source2)
    resource.children.add(resource2)

    url = reverse("resource-list")

    response = admin_client.get(
        url, data={"data_source": data_source.id, "origin_id_exists": False}
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 1

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource2.id}


@pytest.mark.django_db
def test_data_source_and_origin_id_exists_true_different_data_source_in_child(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    data_source2 = data_source_factory()

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source)
    resource_origin_factory(resource=resource, data_source=data_source2)

    resource2 = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source2)
    resource.children.add(resource2)

    url = reverse("resource-list")

    response = admin_client.get(
        url, data={"data_source": data_source.id, "origin_id_exists": True}
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 1

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource.id}


@pytest.mark.django_db
def test_list_resources_parent_and_child_filter_match(admin_client, resource_factory):

    resource_1 = resource_factory()
    resource_2 = resource_factory()
    resource_2.parents.add(resource_1)
    resource_2.save()

    url = reverse("resource-list")

    response = admin_client.get(url, data={"parent": resource_1.id})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 1

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource_2.id}

    response = admin_client.get(url, data={"child": resource_2.id})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 1

    resource_ids = {i["id"] for i in response.data["results"]}

    assert resource_ids == {resource_1.id}


@pytest.mark.django_db
def test_list_resources_parent_and_child_filter_no_match(
    admin_client, resource_factory
):

    resource_1 = resource_factory()
    resource_2 = resource_factory()
    resource_1.parents.add(resource_2)
    resource_1.save()

    url = reverse("resource-list")

    response = admin_client.get(url, data={"parent": resource_1.id})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 0

    response = admin_client.get(url, data={"child": resource_2.id})

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 0


@pytest.mark.django_db
def test_list_resources_filter_by_multiple_resource_ids(
    admin_client, data_source_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    data_source2 = data_source_factory()

    resources = []
    for i in range(1, 10):
        resource = resource_factory()
        resource_origin_factory(resource=resource, data_source=data_source, origin_id=i)
        resources.append(resource)

    resource = resource_factory()
    resource_origin_factory(resource=resource, data_source=data_source, origin_id=1234)
    resource_origin_factory(resource=resource, data_source=data_source2, origin_id=2345)
    resources.append(resource)

    url = reverse("resource-list")

    resource_ids = ",".join(
        [
            "",
            ":",
            str(resources[0].id),
            "{}:{}".format(
                resources[2].origins.first().data_source.id,
                resources[2].origins.first().origin_id,
            ),
            f" {resources[5].id} ",
            "{}:{}".format(
                resources[8].origins.first().data_source.id,
                resources[8].origins.first().origin_id,
            ),
            "{}:{}".format(
                resources[9].origins.first().data_source.id,
                resources[9].origins.first().origin_id,
            ),
            "{}:{}".format(
                resources[9].origins.last().data_source.id,
                resources[9].origins.last().origin_id,
            ),
            "nonsensical value",
            "second::::nonsensical",
        ]
    )

    response = admin_client.get(
        url,
        data={
            "resource_ids": resource_ids,
            "data_source": data_source.id,
        },
    )

    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )

    assert response.data["count"] == 5
