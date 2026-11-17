"""
Sample ETL Job: Extract sales data from CSV, transform, and load to JSON.

This script has an INTENTIONAL BUG for GlueHealer to find and fix:
  - The CSV column is named "price" but the code references "unit_price"
"""
import csv
import json
import os


def extract_data(filepath):
    """Read records from a CSV file."""
    records = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records


def transform_data(records):
    """Clean and transform records."""
    transformed = []
    for record in records:
        cleaned = {
            "product": record["product_name"].strip().upper(),
            "quantity": int(record["quantity"]),
            # BUG: column is "price", not "unit_price"
            "total": int(record["quantity"]) * float(record["unit_price"]),
        }
        transformed.append(cleaned)
    return transformed


def load_data(records, output_path):
    """Write transformed records to JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(records, f, indent=2)
    print(f"Loaded {len(records)} records to {output_path}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, "data", "sales.csv")
    output_path = os.path.join(script_dir, "output", "sales_transformed.json")

    print("Starting ETL job...")
    records = extract_data(input_path)
    print(f"Extracted {len(records)} records")

    transformed = transform_data(records)
    print(f"Transformed {len(transformed)} records")

    load_data(transformed, output_path)
    print("ETL job complete!")


if __name__ == "__main__":
    main()
