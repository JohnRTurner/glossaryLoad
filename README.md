# DataHub Glossary Manager

A Python utility for bulk loading glossary terms into DataHub from CSV files. This example code demonstrates how to interact with DataHub's API to manage business glossaries.

## Features

- Create or update glossary term groups
- Create or update glossary terms with descriptions
- Associate terms with tables and columns
- Add ownership information (technical owners, data stewards, business owners)
- Apply tags to tables and columns

## Installation

### Prerequisites

- Python 3.7+
- Access to a DataHub instance
- DataHub API token

### Setup

1. Clone this repository or download the script:

```bash
git clone https://github.com/yourusername/datahub-glossary-manager.git
cd datahub-glossary-manager
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Deployment

For detailed deployment instructions using Docker, Docker Compose, or Kubernetes, please refer to the [Deployment Guide](DEPLOYMENT.md).

Quick deployment options:
- **Docker**: Use the provided `docker-build-run.sh` script
- **Docker Compose**: Run with `docker-compose up`
- **Kubernetes**: Apply the Kubernetes manifests in the `k8s-deployment.yaml` file

## Configuration

The script can be configured in two ways:

### 1. Command line arguments

```
--csv-file: Path to the CSV file containing glossary terms (required)
--gms-url: DataHub GMS URL (e.g., http://localhost:8080)
--token: DataHub API token
```

### 2. Configuration file

Alternatively, you can store your DataHub credentials in a `~/.datahubenv` file, which will be used automatically if command line arguments are not provided.

Example `~/.datahubenv` file:

```
gms_url=http://your-datahub-instance:8080
token=your_api_token_here
```

The script supports multiple configuration file formats, including YAML-like structures and simple key-value pairs.

## CSV File Format

The CSV file should contain the following columns:

| Column | Description |
| ------ | ----------- |
| Category | The glossary term group/category |
| Business Glossary Term | The glossary term name |
| Business Definition | Description of the term |
| Technical Owner | Email address(es) of the technical owner(s) |
| Data Steward | Email address(es) of the data steward(s) |
| Business Owner | Email address(es) of the business owner(s) |
| Tag | Semicolon-separated list of tags to apply |
| Database.Schema.Table | Database object in format DB.SCHEMA.TABLE |
| Field Name | Column name (optional) |

### Example CSV

```
Category,Business Glossary Term,Business Definition,Technical Owner,Data Steward,Business Owner,Tag,Database.Schema.Table,Field Name
Commercial Loan - Glossary,Accrual Basis,Day-Count Convention to determine how interest accrues overtime on a loan. Its defines how days are counted between two dates and how this affects the calculation of interest.,john.turner@datahub.com,,,PII;Banking,DB_RAW.SCH_IBS.LOAN_NOTE,NOTE_BASIS
Commercial Loan - Glossary,Actual Interest Rate,A nominal interest rate is the stated or advertised interest rate on a loan,john.turner@datahub.com,,,Financial,DB_RAW.SCH_IBS.LOAN_NOTE,NOTE_ORIG_INT_RATE
Commercial Loan - Glossary,Anchor Tenant,Refers to a prominent and well-established tenant who occupies a large portion of a property.,john.turner@datahub.com,,,Real Estate,DB_RAW.SCH_IBS.LOAN_COLLATERAL,LOAN_COLL_NOTE_1
```

## Usage

Run the script with:

```bash
python datahub_glossary_manager.py --csv-file your_glossary_file.csv
```

If you have a `~/.datahubenv` file with your credentials:

```bash
python datahub_glossary_manager.py --csv-file your_glossary_file.csv
```

Or specify the DataHub URL and token explicitly:

```bash
python datahub_glossary_manager.py --csv-file your_glossary_file.csv --gms-url http://your-datahub:8080 --token your-api-token
```

## How It Works

For each row in the CSV file, the script will:

1. Create or update the term group based on the Category column
2. Create or update the glossary term with its description
3. Associate the term with owners (technical, data steward, business)
4. If a table/column is specified, associate the term with the table or column
5. If tags are specified, add them to the table or column

## Implementation Details

The script uses the DataHub REST API for most operations and GraphQL for more complex queries like searching for datasets and fields.

Key functions include:
- Looking up tables by name
- Resolving dataset URNs
- Adding ownership information
- Associating terms with tables and fields
- Applying tags to entities

## Troubleshooting

### Common Issues

1. **Authentication Error**: Make sure your DataHub token is valid and has the correct permissions.

2. **Entity Not Found**: If you get errors about entities not existing, check that the table/column paths are correct.

3. **Import Errors**: Ensure you've installed all the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. **URN Formatting**: Check that your database.schema.table and column names follow the correct format.

### Logging

The script includes detailed logging. You can review the log output to troubleshoot issues. Look for lines starting with:

- `INFO` - Normal operation information
- `WARNING` - Potential issues that didn't halt execution
- `ERROR` - Problems that prevented proper operation

## Disclaimer

This is example code intended for educational purposes. In a production environment, you would want to add proper error handling, testing, and additional security measures.

## License

[Your license information here]

## Contributing

[Your contribution guidelines here]