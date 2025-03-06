import boto3
import csv
import typer


def import_data_from_csv(file_path: str, dynamodb_table_name: str):
    # Initialize DynamoDB client
    dynamodb_client = boto3.client('dynamodb')

    # Read the CSV file from your local machine
    with open(file_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        column_names = reader.fieldnames

        # Push data to DynamoDB
        for row in reader:
            item = {column: {'N': row[column]} if row[column].isnumeric() else {'S': row[column]} for column in
                    column_names}  # Wrap values with {"S": ...}
            dynamodb_client.put_item(TableName=dynamodb_table_name, Item=item)

        print(f"Data from {file_path} has been successfully pushed to DynamoDB table {dynamodb_table_name}.")


def copy_from_table(region: str = typer.Argument(..., help="Region"),
                    profile: str = typer.Argument(..., help="AWS profile"),
                    src_table_name: str = typer.Argument(..., help="Source table name"),
                    dst_table_name: str = typer.Argument(..., help="Destination table name")):
    try:
        boto3.setup_default_session(profile_name=profile, region_name=region)
        dynamodb = boto3.resource('dynamodb')

        table_src = dynamodb.Table(src_table_name)
        table_dst = dynamodb.Table(dst_table_name)

        response = table_src.scan()
        data = response['Items']

        while 'LastEvaluatedKey' in response:  #Se c'è un altro item mi verrà dato in LastEvaluatedKey
            response = table_src.scan(
                ExclusiveStartKey=response['LastEvaluatedKey'])  #Prendo l'item con l'ultimo LastEvaluatedKey ricevuto
            data.extend(response['Items'])

        for item in data:
            table_dst.put_item(Item=item)
    except Exception as e:
        print(e)
