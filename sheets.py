#!/usr/bin/python3
# sheets.py
# from __future__ import print_function
import os
import pandas as pd
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from google.oauth2 import service_account


# -- CREDENTIALS SETUP -- #

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

cred_path = f'{os.path.dirname(os.path.abspath(__file__))}/credentials.json'
credentials = service_account.Credentials.from_service_account_file(cred_path, scopes=SCOPES)

spreadsheet_service = build('sheets', 'v4', credentials=credentials)
drive_service = build('drive', 'v3', credentials=credentials)


# -- METHODS -- #

def create(spreadsheet_name: str) -> str:
    spreadsheet_details = {
        'properties': {
            'title': spreadsheet_name
        }
    }
    spreadsheet = spreadsheet_service.spreadsheets().create(body=spreadsheet_details,
                                                            fields='spreadsheetId').execute()
    spreadsheet_id = spreadsheet.get('spreadsheetId')
    print('Creating Spreadsheet ID: {0}'.format(spreadsheet_id))

    user_file = open("users.txt", "r")
    user_data = user_file.read()
    user_list = user_data.replace('\n', ',').split(',')

    for user in user_list:
        permission1 = {
            'type': 'user',
            'role': 'writer',
            'emailAddress': user
        }
        drive_service.permissions().create(fileId=spreadsheet_id, body=permission1).execute()

    return spreadsheet_id


def add_sheet(spreadsheet_id: str, sheet_name: str):
    body = {
        "requests": {
            "addSheet": {
                "properties": {
                    "title": sheet_name
                }
            }
        }
    }
    try:
        spreadsheet_service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    except HttpError as error:
        print(F'An error occurred: {error}')


def rename_sheet(spreadsheet_id: str, sheet_id: str, new_name: str):
    body = {
        'requests': {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "title": new_name,
                },
                "fields": "title",
            }
        }
    }
    try:
        spreadsheet_service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    except HttpError as error:
        print(F'An error occurred: {error}')


def get_all_spreadsheets():
    try:
        files = []
        page_token = None
        while True:
            # pylint: disable=maybe-no-member
            response = drive_service.files().list(q="mimeType='application/vnd.google-apps.spreadsheet'",
                                                  spaces='drive',
                                                  fields='nextPageToken, ''files(id, name)',
                                                  pageToken=page_token).execute()
            # for file in response.get('files', []):
            #     # Process change
            #     print(F'Found file: {file.get("name")}, {file.get("id")}')
            files.extend(response.get('files', []))
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
    except HttpError as error:
        print(F'An error occurred: {error}')
        files = None

    return files


def find_spreadsheet_by_name(spreadsheet_name: str):
    spreadsheets = get_all_spreadsheets()
    found_sheet = next((item for item in spreadsheets if item['name'] == spreadsheet_name), None)
    return found_sheet['id'] if found_sheet else None


def read_range(spreadsheet_id: str, range_name: str):
    result = spreadsheet_service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    rows = result.get('values', [])
    print('{0} rows retrieved.'.format(len(rows)))
    # print('{0} rows retrieved.'.format(rows))
    return rows


def range_to_pandas_df(sheet_range: list, headers: bool = False):
    if headers:
        return pd.DataFrame(sheet_range[1:], columns=sheet_range[0])
    else:
        return pd.DataFrame(sheet_range)


def read_range_to_pandas_df(spreadsheet_id: str, range_name: str, headers: bool = False):
    return range_to_pandas_df(read_range(spreadsheet_id, range_name), headers)


def export_pandas_df_to_sheets(spreadsheet_id: str, range_name: str, df: pd.core.frame.DataFrame):
    value_input_option = 'USER_ENTERED'
    body = {
        'values': [df.columns.values.tolist()] + df.values.tolist()
    }
    result = spreadsheet_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption=value_input_option, body=body).execute()
    print('{0} cells updated.'.format(result.get('updatedCells')))
