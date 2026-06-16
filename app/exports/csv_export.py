"""CSV export utilities."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..models.business import Business


class CSVExporter:
    """Write qualified leads to the MVP CSV format."""

    COLUMNS = [
        "Business Name",
        "Phone",
        "Address",
        "Website",
        "Has Website",
        "Website Type",
        "Website Quality Score",
        "Priority Score",
        "Notes",
    ]

    def export(self, businesses: list[Business], output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        rows = [business.to_csv_row() for business in businesses]
        dataframe = pd.DataFrame(rows, columns=self.COLUMNS)
        dataframe.to_csv(path, index=False)
        return path
