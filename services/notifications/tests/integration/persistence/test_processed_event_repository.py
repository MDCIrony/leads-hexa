from uuid import uuid4


def test_the_first_mark_is_new_and_a_repeat_is_not(uow_factory):
    event_id = uuid4()
    with uow_factory() as uow:
        assert uow.processed_events.mark("group-a", event_id) is True
        assert uow.processed_events.mark("group-a", event_id) is False


def test_the_same_event_is_new_for_another_consumer(uow_factory):
    event_id = uuid4()
    with uow_factory() as uow:
        assert uow.processed_events.mark("group-a", event_id) is True
        assert uow.processed_events.mark("group-b", event_id) is True
