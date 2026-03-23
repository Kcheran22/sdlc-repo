from databricks import sql
import os
from dotenv import load_dotenv

# 🔥 Load environment variables
load_dotenv()


# ===============================
# 🔹 CONNECTION
# ===============================
def get_connection():
    """
    Create Databricks SQL Warehouse connection
    """
    return sql.connect(
        server_hostname=os.getenv("DATABRICKS_HOST").replace("https://", ""),
        http_path=f"/sql/1.0/warehouses/{os.getenv('DATABRICKS_WAREHOUSE_ID')}",
        access_token=os.getenv("DATABRICKS_TOKEN")
    )


# ===============================
# 🔹 INSERT DATA
# ===============================
def save_to_databricks(
    project_id: str,
    project_name: str,
    cleaned_requirement: str,
    brd: str,
    frd: str
):
    """
    Insert project data into Databricks table
    """

    catalog = os.getenv("DATABRICKS_CATALOG")
    schema = os.getenv("DATABRICKS_SCHEMA")
    table = os.getenv("DATABRICKS_TABLE")

    full_table_name = f"{catalog}.{schema}.{table}"

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # 🔥 Ensure no None values
        cleaned_requirement = cleaned_requirement or ""
        brd = brd or ""
        frd = frd or ""

        query = f"""
        INSERT INTO {full_table_name}
        (project_id, project_name, cleaned_requirement, brd, frd)
        VALUES (?, ?, ?, ?, ?)
        """

        values = (
            project_id,
            project_name,
            cleaned_requirement,
            brd,
            frd
        )

        print("🧪 DEBUG INSERT VALUES:", values)

        cursor.execute(query, values)
        connection.commit()

        print("✅ Data inserted successfully into Databricks")

    except Exception as e:
        print("❌ Error inserting data:", str(e))
        raise Exception(f"Databricks Insert Failed: {str(e)}")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ===============================
# 🔹 FETCH DATA
# ===============================
def fetch_projects():
    """
    Fetch all projects from Databricks
    """

    catalog = os.getenv("DATABRICKS_CATALOG")
    schema = os.getenv("DATABRICKS_SCHEMA")
    table = os.getenv("DATABRICKS_TABLE")

    full_table_name = f"{catalog}.{schema}.{table}"

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = f"""
        SELECT project_id, project_name, cleaned_requirement, brd, frd
        FROM {full_table_name}
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        results = []

        for row in rows:
            results.append({
                "project_id": row[0],
                "project_name": row[1],
                "cleaned_requirement": row[2],
                "brd": row[3],
                "frd": row[4]
            })

        return results

    except Exception as e:
        print("❌ Error fetching data:", str(e))
        raise Exception(f"Databricks Fetch Failed: {str(e)}")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()