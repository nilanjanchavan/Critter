"""Unit tests for the synchronous event bus."""

from dataclasses import dataclass
import pytest
from critter.core.events import Event, EventBus


@dataclass
class PetSpawned(Event):
    pet_id: str
    species: str
    x: int
    y: int


@dataclass
class PetMoved(Event):
    pet_id: str
    new_x: int
    new_y: int


def test_event_publish_and_subscribe():
    bus = EventBus()
    received = []

    def on_spawn(event: PetSpawned):
        received.append((event.pet_id, event.species, event.x, event.y))

    bus.subscribe(PetSpawned, on_spawn)

    bus.publish(PetSpawned(pet_id="doge_1", species="dog", x=100, y=200))

    assert len(received) == 1
    assert received[0] == ("doge_1", "dog", 100, 200)


def test_event_unsubscribe():
    bus = EventBus()
    received = []

    def on_move(event: PetMoved):
        received.append((event.new_x, event.new_y))

    unsubscribe = bus.subscribe(PetMoved, on_move)

    bus.publish(PetMoved(pet_id="doge_1", new_x=10, new_y=20))
    assert len(received) == 1

    unsubscribe()

    bus.publish(PetMoved(pet_id="doge_1", new_x=30, new_y=40))
    assert len(received) == 1  # No new event received


def test_handler_error_isolation():
    bus = EventBus()
    successful_calls = []

    def failing_handler(event: PetSpawned):
        raise ValueError("Simulated handler crash")

    def safe_handler(event: PetSpawned):
        successful_calls.append(event.pet_id)

    bus.subscribe(PetSpawned, failing_handler)
    bus.subscribe(PetSpawned, safe_handler)

    # Publishing should not raise, safe_handler should still be called
    bus.publish(PetSpawned(pet_id="doge_safe", species="dog", x=0, y=0))

    assert successful_calls == ["doge_safe"]


def test_global_subscriber():
    bus = EventBus()
    all_events = []

    bus.subscribe_all(lambda ev: all_events.append(ev.event_name))

    bus.publish(PetSpawned(pet_id="1", species="dog", x=0, y=0))
    bus.publish(PetMoved(pet_id="1", new_x=10, new_y=10))

    assert all_events == ["PetSpawned", "PetMoved"]

