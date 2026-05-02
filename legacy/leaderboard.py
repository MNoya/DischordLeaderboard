import time

from gspread.utils import rowcol_to_a1

import gspread
from google.oauth2.service_account import Credentials

from aggregator import get_draft_data, DraftAggregator
from credentials import SERVICE_ACCOUNT_DICT
from user_ids import PLAYERS

SPREADSHEET_ID = "1aaW2b-qt2sBJCGSNMcnIZiSCKkTKzbNhCs9_IPrXQM8"
WORKSHEET_NAME = "ECL"
ECL_FORMATS = {
    "Premier": ["PremierDraft"],
    "Traditional": ["TradDraft"],
    "LCQ Draft 1": ["LimitedChampionshipQualifier_Draft1"],
    "LCQ Draft 2": ["LimitedChampionshipQualifier_Draft2"],
    "Sealed": ["QualifierPlayInSealed", "ArenaDirect_Sealed", "Sealed", "TradSealed"],
    "Quick": ["QuickDraft", "PickTwoDraft", "Emblem_QuickDraft"],
}

FORMAT_POINTS = {
    "Premier": 10,
    "Traditional": 9,
    "LCQ Draft 1": 30,
    "LCQ Draft 2": 10,  # per Win
    "Sealed": 8,
    "Quick": 3,
}


class SpreadsheetWriter:
    def __init__(self):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_DICT, scopes=scopes)
        client = gspread.authorize(creds)
        self.sheet = client.open_by_key(SPREADSHEET_ID)
        self.worksheet = self.sheet.worksheet(WORKSHEET_NAME)
        self.require_merge = False

        self.player_data = {}

    def get_all_player_data(self):
        for p_tuple in PLAYERS:
            player_name = p_tuple[0]
            player_id = p_tuple[1]
            drafts = get_draft_data(player_id)
            aggregator = DraftAggregator(drafts)

            time.sleep(1)
            print(f"Retrieving ECL Player Data for: {player_name}...")
            self.player_data[player_name] = aggregator.aggregate_ECL()
        print(self.player_data)

    def write_ecl_leaderboard(self, player_data=None):
        if player_data:
            # Allow passing in new data
            self.player_data = player_data
        elif not self.player_data:
            self.get_all_player_data()
        self.build_rows()

        self.worksheet.clear()
        self.worksheet.update("A1", self.rows, value_input_option="USER_ENTERED")

        self.apply_formatting()
        print(f"Updated: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/")

    def build_rows(self):
        print("Building rows...")
        # Header rows
        header_row_1 = ["", ""]
        header_row_2 = ["Player", "Total Score"]

        for format_label in ECL_FORMATS.keys():
            header_row_1.extend([format_label, "", ""])
            if format_label == "LCQ Draft 2":
                header_row_2.extend(["Wins", "Win Rate", "Score"])
            else:
                header_row_2.extend(["Trophies", "Trophy Rate", "Score"])

        rows = [header_row_1, header_row_2]

        # Player rows
        player_rows = []
        for name, player_data in self.player_data.items():
            row = [name]
            total_score = 0
            format_values = []

            for format_label, format_list in ECL_FORMATS.items():
                total_trophies = 0
                total_events = 0

                for fmt in format_list:
                    stats = player_data.get(fmt, {})

                    # LCQ Draft 2 count wins instead of trophies
                    if format_label == "LCQ Draft 2":
                        total_trophies = stats.get("wins", 0) or 0
                    else:
                        total_trophies += stats.get("trophies", 0) or 0
                        total_events += stats.get("events", 0) or 0

                if total_trophies > 0:
                    format_points = FORMAT_POINTS[format_label]
                    if format_label == "LCQ Draft 2":
                        winrate = player_data["LimitedChampionshipQualifier_Draft2"].get("winrate", 0) or 0
                        trophy_rate = winrate
                        format_score = total_trophies * winrate * format_points
                    else:
                        trophy_rate = total_trophies / total_events
                        format_score = (
                                total_trophies
                                * format_points
                                * trophy_rate
                                * (total_trophies / (total_trophies + 2))
                        )

                    total_score += format_score
                else:
                    total_trophies = ""
                    trophy_rate = ""
                    format_score = ""

                format_values.extend([
                    total_trophies,
                    trophy_rate,
                    format_score,
                ])

            row.append(total_score)
            row.extend(format_values)
            player_rows.append(row)

        # Sort by total score (index 1)
        player_rows.sort(key=lambda r: r[1], reverse=True)

        rows.extend(player_rows)
        self.rows = rows  # Store the rows to write later

    def apply_formatting(self):
        print("Formatting...")
        worksheet = self.worksheet
        sheet_id = worksheet.id
        total_cols = 2 + (len(ECL_FORMATS) * 3)

        # ---- Merge Header Row 1 ----
        start_col = 3  # Column C (1-based)
        if self.require_merge:  # time expensive
            for _ in ECL_FORMATS:
                start = rowcol_to_a1(1, start_col)
                end = rowcol_to_a1(1, start_col + 2)

                worksheet.merge_cells(f"{start}:{end}")

                worksheet.format(
                    f"{start}:{end}",
                    {
                        "textFormat": {"bold": True},
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                )

                start_col += 3

        # ---- Bold Second Header Row ----
        worksheet.format(
            f"A2:{rowcol_to_a1(2, total_cols)}",
            {"textFormat": {"bold": True}}
        )

        # ---- Percent Formatting ----
        requests = []
        start_row_index = 2  # row 3 (0-based)

        # Column indices (0-based)
        score_col_index = 1  # B
        trophy_col_index = 3  # D

        for _ in range(len(ECL_FORMATS) + 1):
            # ---- PERCENT COLUMN FORMATTING ----
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row_index,
                        "startColumnIndex": trophy_col_index,
                        "endColumnIndex": trophy_col_index + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {
                                "type": "PERCENT",
                                "pattern": "0.0%"
                            }
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat"
                }
            })

            # ---- SCORE COLUMN FORMATTING ----
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row_index,
                        "startColumnIndex": score_col_index,
                        "endColumnIndex": score_col_index + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {
                                "type": "NUMBER",
                                "pattern": "0.0"
                            }
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat"
                }
            })

            trophy_col_index += 3
            score_col_index += 3

        # ---- HEADER BLOCK COLORS ----
        start_col = 2  # Column C (0-based)
        start_row = 0  # Row 1 (0-based)
        end_row = 2  # Up to row 2
        format_colors = [
            {"red": 0.88, "green": 0.95, "blue": 0.88},  # light green
            {"red": 0.85, "green": 0.93, "blue": 0.98},  # light blue
            {"red": 0.99, "green": 0.97, "blue": 0.80},  # light yellow
            {"red": 0.95, "green": 0.90, "blue": 0.80},  # light orange
            {"red": 0.90, "green": 0.85, "blue": 0.95},  # light purple
            {"red": 0.98, "green": 0.88, "blue": 0.90},  # light pink
        ]
        color_index = 0

        for _ in ECL_FORMATS:
            color = format_colors[color_index % len(format_colors)]

            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row,
                        "endRowIndex": end_row,
                        "startColumnIndex": start_col,
                        "endColumnIndex": start_col + 3,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": color
                        }
                    },
                    "fields": "userEnteredFormat.backgroundColor"
                }
            })

            start_col += 3
            color_index += 1

        # ---- Resize Columns ----
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": total_cols,
                },
                "properties": {
                    "pixelSize": 90
                },
                "fields": "pixelSize"
            }
        })

        if requests:
            worksheet.spreadsheet.batch_update({"requests": requests})

        # ---- Freeze ----
        worksheet.freeze(rows=2, cols=2)
