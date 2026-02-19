from __future__ import annotations

import html


def _escape(value: object) -> str:
    return html.escape(str(value))


def transactions_feed_html(transactions: list[dict]) -> str:
    if not transactions:
        return '<div class="empty-state">No recent activity.</div>'

    rows = []
    for item in transactions:
        meta_parts = []
        if item.get("faab") is not None:
            meta_parts.append(f"FAAB ${item['faab']}")
        if item.get("priority") is not None:
            meta_parts.append(f"Priority {item['priority']}")
        meta = " · ".join(meta_parts)
        meta_html = f'<div class="transaction-meta">{_escape(meta)}</div>' if meta else ""
        badge_style = ""
        if item.get("team_color"):
            badge_style = f"background:{_escape(item['team_color'])};"
        rows.append(
            f"""
            <div class="transaction-row">
                <div class="transaction-left">
                    <div class="transaction-badge" style="{badge_style}">{_escape(item['team_badge'])}</div>
                    <div>
                        <div class="transaction-detail">{_escape(item['detail'])}</div>
                        <div class="transaction-type">{_escape(item['type'])}</div>
                        {meta_html}
                    </div>
                </div>
                <div class="transaction-time">{_escape(item['time_label'])}</div>
            </div>
            """
        )
    return f'<div class="transactions-feed">{"".join(rows)}</div>'
