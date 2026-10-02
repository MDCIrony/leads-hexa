from infrastructure.adapters.input.consumers.groups import CONSUMER_GROUPS, DLQ_TOPIC_SPECS


def test_the_groups_and_their_topics_are_the_agreed_ones():
    assert CONSUMER_GROUPS == {
        "notifications.lead-events": "internal.lead-core.events",
        "notifications.intake-events": "internal.intake.events",
        "notifications.members": "internal.identity.agents",
    }


def test_every_group_has_a_single_partition_dead_letter_topic_with_delete_cleanup():
    assert {spec.name for spec in DLQ_TOPIC_SPECS} == {f"internal.dlq.{group}" for group in CONSUMER_GROUPS}
    for spec in DLQ_TOPIC_SPECS:
        assert spec.partitions == 1
        assert spec.config["cleanup.policy"] == "delete"
        assert spec.config["retention.ms"] == "604800000"
