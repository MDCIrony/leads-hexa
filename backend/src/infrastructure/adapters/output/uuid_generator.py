from uuid import UUID, uuid4

from application.ports.output.id_generator_port import IdGeneratorPort


class UuidGenerator(IdGeneratorPort):
    def new_id(self) -> UUID:
        return uuid4()
