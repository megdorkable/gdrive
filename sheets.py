#!/usr/bin/python3
# sheets.py
# from __future__ import print_function
import os
import pandas as pd
from typing import List
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.auth.exceptions import MalformedError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


# -- CREDENTIALS SETUP -- #

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

cred_path = f'{os.path.dirname(os.path.abspath(__file__))}/credentials.json'
token_path = f'{os.path.dirname(os.path.abspath(__file__))}/token.json'
try:
    credentials = service_account.Credentials.from_service_account_file(cred_path, scopes=SCOPES)
except MalformedError:
    credentials = None
    if os.path.exists(token_path):
        credentials = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            credentials = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(credentials.to_json())

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

    try:
        users_path = f'{os.path.dirname(os.path.abspath(__file__))}/users.txt'
        user_file = open(users_path, "r")
        user_data = user_file.read()
        user_list = user_data.replace('\n', ',').split(',')

        for user in user_list:
            permission1 = {
                'type': 'user',
                'role': 'writer',
                'emailAddress': user
            }
            drive_service.permissions().create(fileId=spreadsheet_id, body=permission1).execute()
    except FileNotFoundError as error:
        print(F'Not shared with any additional users: {error}')

    return spreadsheet_id


def find_sheet(spreadsheet_id: str, sheet_name: str):
    try:
        ss = spreadsheet_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheet_id = None
        for sheet in ss['sheets']:
            if sheet['properties']['title'] == sheet_name:
                sheet_id = sheet['properties']['sheetId']
        return sheet_id
    except HttpError as error:
        print(F'An error occurred: {error}')


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


def delete_sheet(spreadsheet_id: str, sheet_name: str):
    sheet_id = find_sheet(spreadsheet_id, sheet_name)
    if sheet_id is not None:
        body = {
            "requests": {
                "deleteSheet": {
                    "sheetId": sheet_id
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
    try:
        result = spreadsheet_service.spreadsheets().values().get(spreadsheetId=spreadsheet_id,
                                                                 range=range_name).execute()
        rows = result.get('values', [])
        print('{0} rows retrieved.'.format(len(rows)))
        # print('{0} rows retrieved.'.format(rows))
        return rows
    except HttpError as error:
        print(f"An error occurred: {error}")
        return []


def write_range(spreadsheet_id: str, range_name: str, values: List[List]):
    value_input_option = 'USER_ENTERED'
    body = {
        'values': values
    }
    result = spreadsheet_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption=value_input_option, body=body).execute()
    print('{0} cells updated.'.format(result.get('updatedCells')))


def range_to_pandas_df(sheet_range: list, headers: bool = False):
    if headers:
        return pd.DataFrame(sheet_range[1:], columns=sheet_range[0])
    else:
        return pd.DataFrame(sheet_range)


def read_range_to_pandas_df(spreadsheet_id: str, range_name: str, headers: bool = False):
    return range_to_pandas_df(read_range(spreadsheet_id, range_name), headers)


def export_pandas_df_to_sheets(spreadsheet_id: str, range_name: str, df: pd.core.frame.DataFrame):
    write_range(spreadsheet_id, range_name, [df.columns.values.tolist()] + df.values.tolist())
