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
