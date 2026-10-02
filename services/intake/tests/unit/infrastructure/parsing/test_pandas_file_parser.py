import uuid

from infrastructure.adapters.output.parsing.pandas_file_parser import PandasFileParser


def _parse(content: bytes, filename: str = "leads.csv"):
    return PandasFileParser().parse_leads_file(content, filename, uuid.uuid4(), uuid.uuid4())


def test_a_csv_becomes_one_command_per_row_with_the_unknown_columns_as_custom_attributes():
    commands = _parse(b"""first_name,last_name,email,company,budget,industry,employee_count
Maria,Gomez,mgomez@techcorp.com,TechCorp Inc,15000,Technology,150
Juan,Perez,jperez@smallbiz.es,SmallBiz Local,800,Retail,10
""")

    assert len(commands) == 2
    assert commands[0].first_name == "Maria"
    assert commands[0].email == "mgomez@techcorp.com"
    assert commands[0].budget == 15000.0
    assert commands[0].custom_attributes.get("employee_count") == 150


def test_the_ids_come_from_the_caller_and_not_from_the_file():
    tenant_id, source_id = uuid.uuid4(), uuid.uuid4()

    [command] = PandasFileParser().parse_leads_file(
        b"first_name,tenant_id\nAna,evil\n", "leads.csv", tenant_id, source_id)

    assert (command.tenant_id, command.source_id) == (tenant_id, source_id)


def test_a_blank_email_cell_becomes_none():
    [command] = _parse(b"first_name,last_name,email,company,budget,industry\nJuan,Perez,,SmallBiz,800,Retail\n")

    assert command.email is None


def test_an_empty_text_cell_is_blank_and_not_the_word_nan():
    """`str(NaN)` is "nan", and that string used to travel all the way out: a private
    customer showed up in the buyer's inbox as working for a company called "nan"."""
    [command] = _parse(b"first_name,last_name,email,company,budget,industry\nJuan,Perez,jperez@x.test,,800,\n")

    assert (command.company, command.industry) == ("", "")


def test_a_non_numeric_budget_only_costs_its_own_row():
    """ProcessBatchUseCase reads any parse failure as an unreadable file and records
    nothing, so raising on one typed cell used to lose every good row around it."""
    commands = _parse(b"""first_name,last_name,email,company,budget,industry
Ana,Uno,ana@x.test,Buena,12000,Tech
Teresa,Dos,teresa@x.test,Mala,por determinar,Tech
Luis,Tres,luis@x.test,Otra,9000,Retail
""")

    assert [c.budget for c in commands] == [12000.0, "por determinar", 9000.0]


def test_a_blank_phone_cell_is_none_and_not_an_empty_string():
    [command] = _parse(b"first_name,last_name,email,phone,company,budget,industry\nJuan,Perez,j@x.test,,Co,800,Retail\n")

    assert command.phone is None


def test_headers_are_normalised():
    [command] = _parse(b" First Name ,LAST_NAME\nAna,Diaz\n")

    assert (command.first_name, command.last_name) == ("Ana", "Diaz")
