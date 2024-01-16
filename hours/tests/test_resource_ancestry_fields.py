import pytest

from hours.models import Resource


@pytest.mark.django_db
def test_ancestry_no_values(resource_factory):
    resource = resource_factory(name="resource1")

    resource2 = resource_factory(name="resource2")
    resource2.parents.add(resource)

    resource2 = Resource.objects.get(pk=resource2.id)

    assert resource2.ancestry_is_public is True
    assert resource2.ancestry_organization == []
    assert resource2.ancestry_data_source == []


@pytest.mark.django_db
def test_ancestry_when_parent_added(
    data_source_factory, organization_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    organization = organization_factory(
        id="12345", name="Test org", data_source=data_source
    )

    resource = resource_factory(name="resource1", organization=organization)
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory(name="resource2")
    resource2.parents.add(resource)

    resource2 = Resource.objects.get(pk=resource2.id)

    assert resource2.ancestry_is_public is True
    assert resource2.ancestry_organization == [organization.id]
    assert resource2.ancestry_data_source == [data_source.id]


@pytest.mark.django_db
def test_ancestry_when_child_added(
    data_source_factory, organization_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    organization = organization_factory(
        id="12345", name="Test org", data_source=data_source
    )

    resource = resource_factory(name="resource1", organization=organization)
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory(name="resource2")
    resource.children.add(resource2)

    resource2 = Resource.objects.get(pk=resource2.id)

    assert resource2.ancestry_is_public is True
    assert resource2.ancestry_organization == [organization.id]
    assert resource2.ancestry_data_source == [data_source.id]


@pytest.mark.django_db
def test_ancestry_when_parent_removed(
    data_source_factory, organization_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    organization = organization_factory(
        id="12345", name="Test org", data_source=data_source
    )

    resource = resource_factory(name="resource1", organization=organization)
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory(name="resource2")
    resource.children.add(resource2)

    resource2 = Resource.objects.get(pk=resource2.id)

    assert resource2.ancestry_is_public is True
    assert resource2.ancestry_organization == [organization.id]
    assert resource2.ancestry_data_source == [data_source.id]

    resource2.parents.remove(resource)

    resource2 = Resource.objects.get(pk=resource2.id)

    assert resource2.ancestry_is_public is None
    assert resource2.ancestry_organization == []
    assert resource2.ancestry_data_source == []


@pytest.mark.django_db
def test_ancestry_when_child_removed(
    data_source_factory, organization_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    organization = organization_factory(
        id="12345", name="Test org", data_source=data_source
    )

    resource = resource_factory(name="resource1", organization=organization)
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory(name="resource2")
    resource.children.add(resource2)

    resource2 = Resource.objects.get(pk=resource2.id)

    assert resource2.ancestry_is_public is True
    assert resource2.ancestry_organization == [organization.id]
    assert resource2.ancestry_data_source == [data_source.id]

    resource.children.remove(resource2)

    resource2 = Resource.objects.get(pk=resource2.id)

    assert resource2.ancestry_is_public is None
    assert resource2.ancestry_organization == []
    assert resource2.ancestry_data_source == []


@pytest.mark.django_db
def test_ancestry_when_parents_cleared(
    data_source_factory, organization_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    organization = organization_factory(
        id="12345", name="Test org", data_source=data_source
    )

    resource = resource_factory(name="resource1", organization=organization)
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory(name="resource2")
    resource.children.add(resource2)

    resource2 = Resource.objects.get(pk=resource2.id)

    assert resource2.ancestry_is_public is True
    assert resource2.ancestry_organization == [organization.id]
    assert resource2.ancestry_data_source == [data_source.id]

    resource2.parents.clear()

    resource2 = Resource.objects.get(pk=resource2.id)

    assert resource2.ancestry_is_public is None
    assert resource2.ancestry_organization == []
    assert resource2.ancestry_data_source == []


@pytest.mark.django_db
def test_ancestry_when_one_child_cleared(
    data_source_factory, organization_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    organization = organization_factory(
        id="12345", name="Test org", data_source=data_source
    )

    resource = resource_factory(name="resource1", organization=organization)
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory(name="resource2")
    resource.children.add(resource2)

    resource2 = Resource.objects.get(pk=resource2.id)

    assert resource2.ancestry_is_public is True
    assert resource2.ancestry_organization == [organization.id]
    assert resource2.ancestry_data_source == [data_source.id]

    resource.children.clear()

    resource2 = Resource.objects.get(pk=resource2.id)

    assert resource2.ancestry_is_public is None
    assert resource2.ancestry_organization == []
    assert resource2.ancestry_data_source == []


@pytest.mark.django_db
def test_ancestry_when_multiple_children_cleared(
    data_source_factory, organization_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    organization = organization_factory(
        id="12345", name="Test org", data_source=data_source
    )

    resource = resource_factory(name="resource1", organization=organization)
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory(name="resource2")
    resource3 = resource_factory(name="resource2")
    resource.children.add(resource2, resource3)

    resource2 = Resource.objects.get(pk=resource2.id)
    resource3 = Resource.objects.get(pk=resource3.id)

    assert resource2.ancestry_is_public is True
    assert resource2.ancestry_organization == [organization.id]
    assert resource2.ancestry_data_source == [data_source.id]
    assert resource3.ancestry_is_public is True
    assert resource3.ancestry_organization == [organization.id]
    assert resource3.ancestry_data_source == [data_source.id]

    resource.children.clear()

    resource2 = Resource.objects.get(pk=resource2.id)
    resource3 = Resource.objects.get(pk=resource3.id)

    assert resource2.ancestry_is_public is None
    assert resource2.ancestry_organization == []
    assert resource2.ancestry_data_source == []
    assert resource3.ancestry_is_public is None
    assert resource3.ancestry_organization == []
    assert resource3.ancestry_data_source == []


@pytest.mark.django_db
def test_ancestry_when_parent_added_to_parent(
    data_source_factory, organization_factory, resource_factory, resource_origin_factory
):
    data_source = data_source_factory()
    organization = organization_factory(
        id="12345", name="Test org", data_source=data_source
    )

    resource = resource_factory(name="resource1", organization=organization)
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory(name="resource2")

    resource3 = resource_factory(name="resource3")
    resource3.parents.add(resource2)

    resource2 = Resource.objects.get(pk=resource2.id)
    resource3 = Resource.objects.get(pk=resource3.id)

    assert resource2.ancestry_is_public is None
    assert resource2.ancestry_organization is None
    assert resource2.ancestry_data_source is None

    assert resource3.ancestry_is_public is True
    assert resource3.ancestry_organization == []
    assert resource3.ancestry_data_source == []

    resource2.parents.add(resource)

    resource2 = Resource.objects.get(pk=resource2.id)
    resource3 = Resource.objects.get(pk=resource3.id)

    assert resource2.ancestry_is_public is True
    assert resource2.ancestry_organization == [organization.id]
    assert resource2.ancestry_data_source == [data_source.id]

    assert resource3.ancestry_is_public is True
    assert resource3.ancestry_organization == [organization.id]
    assert resource3.ancestry_data_source == [data_source.id]


@pytest.mark.django_db
def test_ancestry_multiple_organizations(
    assert_count_equal,
    data_source_factory,
    organization_factory,
    resource_factory,
    resource_origin_factory,
):
    data_source = data_source_factory()
    organization = organization_factory(
        id="1", name="Test org 1", data_source=data_source, origin_id="1"
    )
    organization2 = organization_factory(
        id="2", name="Test org 2", data_source=data_source, origin_id="2"
    )

    resource = resource_factory(name="resource1", organization=organization)
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory(name="resource2", organization=organization2)
    resource_origin_factory(resource=resource2, data_source=data_source)
    resource2.parents.add(resource)

    resource3 = resource_factory(name="resource3")
    resource3.parents.add(resource2)

    resource3 = Resource.objects.get(pk=resource3.id)

    assert resource3.ancestry_is_public is True
    assert_count_equal(
        resource3.ancestry_organization, [organization.id, organization2.id]
    )
    assert resource3.ancestry_data_source == [data_source.id]


@pytest.mark.django_db
def test_ancestry_multiple_data_sources(
    assert_count_equal,
    data_source_factory,
    organization_factory,
    resource_factory,
    resource_origin_factory,
):
    data_source = data_source_factory()
    data_source2 = data_source_factory()

    organization = organization_factory(
        id="1", name="Test org 1", data_source=data_source, origin_id="1"
    )

    resource = resource_factory(name="resource1", organization=organization)
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory(name="resource2", organization=organization)
    resource_origin_factory(resource=resource2, data_source=data_source2)
    resource2.parents.add(resource)

    resource3 = resource_factory(name="resource3")
    resource3.parents.add(resource2)

    resource3 = Resource.objects.get(pk=resource3.id)

    assert resource3.ancestry_is_public is True
    assert resource3.ancestry_organization == [organization.id]
    assert_count_equal(
        resource3.ancestry_data_source, [data_source.id, data_source2.id]
    )


@pytest.mark.django_db
def test_ancestry_multiple_organizations_and_data_sources(
    assert_count_equal,
    data_source_factory,
    organization_factory,
    resource_factory,
    resource_origin_factory,
):
    data_source = data_source_factory()
    data_source2 = data_source_factory()

    organization = organization_factory(
        id="1", name="Test org 1", data_source=data_source, origin_id="1"
    )
    organization2 = organization_factory(
        id="2", name="Test org 2", data_source=data_source2, origin_id="2"
    )

    resource = resource_factory(name="resource1", organization=organization)
    resource_origin_factory(resource=resource, data_source=data_source)

    resource2 = resource_factory(name="resource2", organization=organization2)
    resource_origin_factory(resource=resource2, data_source=data_source2)
    resource2.parents.add(resource)

    resource3 = resource_factory(name="resource3")
    resource3.parents.add(resource2)

    resource3 = Resource.objects.get(pk=resource3.id)

    assert resource3.ancestry_is_public is True
    assert_count_equal(
        resource3.ancestry_organization, [organization.id, organization2.id]
    )
    assert_count_equal(
        resource3.ancestry_data_source, [data_source.id, data_source2.id]
    )


#
# Resource.get_ancestors
#
@pytest.mark.django_db
def test_get_ancestors_empty(resource_factory):
    resource = resource_factory(name="resource1")

    assert resource.get_ancestors() == set()


@pytest.mark.django_db
def test_get_ancestors_one_parent(resource_factory):
    resource = resource_factory(name="resource1")
    resource2 = resource_factory(name="resource2")

    resource.parents.add(resource2)

    assert resource.get_ancestors() == {resource2}


@pytest.mark.django_db
def test_get_ancestors_two_parents(resource_factory):
    resource = resource_factory(name="resource1")
    resource2 = resource_factory(name="resource2")
    resource3 = resource_factory(name="resource3")

    resource.parents.add(resource2)
    resource.parents.add(resource3)

    assert resource.get_ancestors() == {resource2, resource3}


@pytest.mark.django_db
def test_get_ancestors_one_grandparent(resource_factory):
    resource = resource_factory(name="resource1")
    resource2 = resource_factory(name="resource2")
    resource3 = resource_factory(name="resource3")

    resource.parents.add(resource2)
    resource2.parents.add(resource3)

    assert resource.get_ancestors() == {resource2, resource3}


@pytest.mark.django_db
def test_get_ancestors_two_grandparents(resource_factory):
    resource = resource_factory(name="resource1")
    resource2 = resource_factory(name="resource2")
    resource3 = resource_factory(name="resource3")
    resource4 = resource_factory(name="resource4")

    resource.parents.add(resource2)
    resource2.parents.add(resource3)
    resource2.parents.add(resource4)

    assert resource.get_ancestors() == {resource2, resource3, resource4}


@pytest.mark.django_db
def test_get_ancestors_two_grandparents_two_branches(resource_factory):
    resource = resource_factory(name="resource1")
    resource2 = resource_factory(name="resource2")
    resource3 = resource_factory(name="resource3")
    resource4 = resource_factory(name="resource4")
    resource5 = resource_factory(name="resource5")

    resource.parents.add(resource2)
    resource.parents.add(resource3)

    resource2.parents.add(resource4)
    resource3.parents.add(resource5)

    assert resource.get_ancestors() == {resource2, resource3, resource4, resource5}


# TODO: this works, but signals.resource_children_changed doesn't work with loops
# @pytest.mark.django_db
# def test_get_ancestors_grandparent_loop(resource_factory):
#     resource = resource_factory(name="resource1")
#     resource2 = resource_factory(name="resource2")
#     resource3 = resource_factory(name="resource3")
#
#     resource.parents.add(resource2)
#     resource2.parents.add(resource3)
#     resource3.parents.add(resource)
#
#     assert resource.get_ancestors() == {resource, resource2, resource3}


#
# Resource.get_descendants
#
@pytest.mark.django_db
def test_get_descendants_empty(resource_factory):
    resource = resource_factory(name="resource1")

    assert resource.get_descendants() == set()


@pytest.mark.django_db
def test_get_descendants_one_child(resource_factory):
    resource = resource_factory(name="resource1")
    resource2 = resource_factory(name="resource2")

    resource.children.add(resource2)

    assert resource.get_descendants() == {resource2}


@pytest.mark.django_db
def test_get_descendants_children(resource_factory):
    resource = resource_factory(name="resource1")
    resource2 = resource_factory(name="resource2")
    resource3 = resource_factory(name="resource3")

    resource.children.add(resource2)
    resource.children.add(resource3)

    assert resource.get_descendants() == {resource2, resource3}


@pytest.mark.django_db
def test_get_descendants_one_grandchild(resource_factory):
    resource = resource_factory(name="resource1")
    resource2 = resource_factory(name="resource2")
    resource3 = resource_factory(name="resource3")

    resource.children.add(resource2)
    resource2.children.add(resource3)

    assert resource.get_descendants() == {resource2, resource3}


@pytest.mark.django_db
def test_get_descendants_two_grandchildren(resource_factory):
    resource = resource_factory(name="resource1")
    resource2 = resource_factory(name="resource2")
    resource3 = resource_factory(name="resource3")
    resource4 = resource_factory(name="resource4")

    resource.children.add(resource2)
    resource2.children.add(resource3)
    resource2.children.add(resource4)

    assert resource.get_descendants() == {resource2, resource3, resource4}


@pytest.mark.django_db
def test_get_descendants_two_grandchildren_two_branches(resource_factory):
    resource = resource_factory(name="resource1")
    resource2 = resource_factory(name="resource2")
    resource3 = resource_factory(name="resource3")
    resource4 = resource_factory(name="resource4")
    resource5 = resource_factory(name="resource5")

    resource.children.add(resource2)
    resource.children.add(resource3)

    resource2.children.add(resource4)
    resource3.children.add(resource5)

    assert resource.get_descendants() == {resource2, resource3, resource4, resource5}
