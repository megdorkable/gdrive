#!/usr/bin/env python3
# gdrive.py
import logging
import os

import google.auth.exceptions as exceptions
import gspread
from tenacity import retry_if_exception


class retry_if_api_429_error(retry_if_exception):

    def __init__(self):

        def is_api_429_error(exception):
            return (isinstance(exception, gspread.exceptions.APIError) and exception.args[0]["code"] == 429)

        super().__init__(predicate=is_api_429_error)


def after_exception_log(retry_state):
    logging.error(f"API call limit reached, retrying (attempt count: {retry_state.attempt_number})...")


class SheetsOAuth:

    def __init__(self, credentials_filepath: str, authorized_user_filepath: str):
        self.cred_path = credentials_filepath
        self.authuser_path = authorized_user_filepath

    def open(self, sh_name) -> gspread.Spreadsheet:
        gc = gspread.oauth(
            credentials_filename=self.cred_path,
            authorized_user_filename=self.authuser_path,
        )

        try:
            sh = gc.open(sh_name)
        except gspread.exceptions.SpreadsheetNotFound:
            sh = gc.create(sh_name)
        except exceptions.RefreshError:
            os.remove(self.authuser_path)
            return open(sh_name)

        return sh
