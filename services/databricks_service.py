from databricks import sql
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_connection():
    """
    Create Databricks SQL Warehouse connection
    """
    return sql.connect(
        server_hostname=os.getenv("DATABRICKS_HOST").replace("https://", ""),
        http_path=f"/sql/1.0/warehouses/{os.getenv('DATABRICKS_WAREHOUSE_ID')}",
        access_token=os.getenv("DATABRICKS_TOKEN")
    )


def save_to_databricks(project_id: str, project_name: str, cleaned_requirement: str):
    """
    Insert project data into Databricks table
    """

    catalog = os.getenv("DATABRICKS_CATALOG")
    schema = os.getenv("DATABRICKS_SCHEMA")
    table = os.getenv("DATABRICKS_TABLE")

    full_table_name = f"{catalog}.{schema}.{table}"

    connection = get_connection()
    cursor = connection.cursor()

    try:
        query = f"""
        INSERT INTO {full_table_name}
        (project_id, project_name, cleaned_requirement)
        VALUES (?, ?, ?)
        """

        cursor.execute(query, (project_id, project_name, cleaned_requirement))
        connection.commit()

        print("✅ Data inserted successfully into Databricks")

    except Exception as e:
        print("❌ Error inserting data:", str(e))
        raise e

    finally:
        cursor.close()
        connection.close()


def fetch_projects():
    """
    Fetch all projects (optional API use)
    """

    catalog = os.getenv("DATABRICKS_CATALOG")
    schema = os.getenv("DATABRICKS_SCHEMA")
    table = os.getenv("DATABRICKS_TABLE")

    full_table_name = f"{catalog}.{schema}.{table}"

    connection = get_connection()
    cursor = connection.cursor()

    try:
        query = f"SELECT * FROM {full_table_name}"
        cursor.execute(query)

        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                "project_id": row[0],
                "project_name": row[1],
                "cleaned_requirement": row[2]
            })

        return results

    except Exception as e:
        print("❌ Error fetching data:", str(e))
        raise e

    finally:
        cursor.close()
        connection.close()