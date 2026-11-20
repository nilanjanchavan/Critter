"""Unit tests for PetManager."""

import pytest
from critter.core.events import EventBus
from critter.core.manager import PetManager, PetNotFoundError
from critter.core.registry import PetRegistry


@pytest.fixture
def manager():
    registry = PetRegistry(search_paths=["packages/pets"])
    bus = EventBus()
    return PetManager(registry=registry, event_bus=bus)


def test_spawn_pet(manager):
    inst = manager.spawn("dog", custom_name="Barnaby")
    assert inst.instance_id == "dog_1"
    assert inst.custom_name == "Barnaby"
    assert inst.manifest.id == "dog"
    assert len(manager.list_instances()) == 1


def test_spawn_multiple_instances(manager):
    dog1 = manager.spawn("dog")
    dog2 = manager.spawn("dog")
    cat1 = manager.spawn("cat", custom_name="Mochi-chan")

    assert dog1.instance_id == "dog_1"
    assert dog2.instance_id == "dog_2"
    assert cat1.instance_id == "cat_1"
    assert cat1.custom_name == "Mochi-chan"
    assert len(manager.list_instances()) == 3


def test_remove_pet(manager):
    inst = manager.spawn("cat")
    assert manager.get_instance(inst.instance_id) is not None

    removed = manager.remove(inst.instance_id)
    assert removed is True
    assert manager.get_instance(inst.instance_id) is None
    assert len(manager.list_instances()) == 0


def test_pause_and_resume_all(manager):
    dog = manager.spawn("dog")
    cat = manager.spawn("cat")

    assert not dog.controller.is_paused
    assert not cat.controller.is_paused

    manager.pause_all()
    assert dog.controller.is_paused
    assert cat.controller.is_paused

    manager.resume_all()
    assert not dog.controller.is_paused
    assert not cat.controller.is_paused


def test_pause_individual(manager):
    dog = manager.spawn("dog")
    cat = manager.spawn("cat")

    manager.pause_instance(dog.instance_id)
    assert dog.controller.is_paused
    assert not cat.controller.is_paused


def test_spawn_unknown_package(manager):
    with pytest.raises(PetNotFoundError, match="not found in registry"):
        manager.spawn("dragon")


def test_hide_and_show(manager):
    cat = manager.spawn("cat")
    assert cat.is_visible is True

    manager.hide_instance(cat.instance_id)
    assert cat.is_visible is False

    manager.show_instance(cat.instance_id)
    assert cat.is_visible is True
