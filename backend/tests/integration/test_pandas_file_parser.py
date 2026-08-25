import uuid
from infrastructure.adapters.output.parsers.pandas_file_parser import PandasFileParser

def test_pandas_file_parser_csv():
    csv_content = b"""first_name,last_name,email,company,budget,industry,employee_count
Maria,Gomez,mgomez@techcorp.com,TechCorp Inc,15000,Technology,150
Juan,Perez,jperez@smallbiz.es,SmallBiz Local,800,Retail,10
"""
    parser = PandasFileParser()
    tenant_id = uuid.uuid4()
    source_id = uuid.uuid4()
    commands = parser.parse_leads_file(csv_content, "leads.csv", tenant_id, source_id)

    assert len(commands) == 2
    assert commands[0].first_name == "Maria"
    assert commands[0].email == "mgomez@techcorp.com"
    assert commands[0].budget == 15000.0
    assert commands[0].custom_attributes.get("employee_count") == 150


def test_pandas_file_parser_blank_email_cell_becomes_none():
    csv_content = b"""first_name,last_name,email,company,budget,industry
Juan,Perez,,SmallBiz Local,800,Retail
"""
    parser = PandasFileParser()
    tenant_id = uuid.uuid4()
    source_id = uuid.uuid4()
    commands = parser.parse_leads_file(csv_content, "leads.csv", tenant_id, source_id)

    assert len(commands) == 1
    assert commands[0].email is None


def test_an_empty_text_cell_is_blank_and_not_the_word_nan():
    """`str(NaN)` is "nan", and that string used to travel all the way out: a
    private customer showed up in the buyer's inbox as working for a company
    called "nan", and an IS_EMPTY rule on the field never fired."""
    csv_content = b"""first_name,last_name,email,company,budget,industry
Juan,Perez,jperez@x.test,,800,
"""
    commands = PandasFileParser().parse_leads_file(
        csv_content, "leads.csv", uuid.uuid4(), uuid.uuid4()
    )

    assert commands[0].company == ""
    assert commands[0].industry == ""


def test_a_non_numeric_budget_only_costs_its_own_row():
    """ProcessBatchUseCase reads any parse failure as an unreadable file and
    records nothing, so raising on one typed cell used to lose every good row
    around it. The cell travels on instead, for the domain to reject."""
    csv_content = b"""first_name,last_name,email,company,budget,industry
Ana,Uno,ana@x.test,Buena,12000,Tech
Teresa,Dos,teresa@x.test,Mala,por determinar,Tech
Luis,Tres,luis@x.test,Otra,9000,Retail
"""
    commands = PandasFileParser().parse_leads_file(
        csv_content, "leads.csv", uuid.uuid4(), uuid.uuid4()
    )

    assert len(commands) == 3
    assert commands[0].budget == 12000.0
    assert commands[1].budget == "por determinar"
    assert commands[2].budget == 9000.0


def test_a_blank_phone_cell_is_none_and_not_an_empty_string():
    csv_content = b"""first_name,last_name,email,phone,company,budget,industry
Juan,Perez,jperez@x.test,,SmallBiz,800,Retail
"""
    commands = PandasFileParser().parse_leads_file(
        csv_content, "leads.csv", uuid.uuid4(), uuid.uuid4()
    )

    assert commands[0].phone is None
