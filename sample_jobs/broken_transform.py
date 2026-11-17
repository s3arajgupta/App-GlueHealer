"""
Sample Data Transformation Job: Calculate user engagement metrics.

This script has TWO INTENTIONAL BUGS for GlueHealer to find and fix:
  1. Division by zero — user with 0 sessions causes ZeroDivisionError
  2. KeyError — code references "active" but the field is "is_active"
"""
import json


def load_users(data_str):
    """Parse JSON user data."""
    return json.loads(data_str)


def calculate_metrics(users):
    """Calculate user engagement metrics."""
    metrics = []
    for user in users:
        # BUG 1: ZeroDivisionError when sessions == 0
        avg_duration = user["total_duration"] / user["sessions"]
        # BUG 2: KeyError — field is "is_active", not "active"
        status = "active" if user["active"] else "inactive"
        metrics.append(
            {
                "user_id": user["id"],
                "avg_session_duration": avg_duration,
                "status": status,
            }
        )
    return metrics


def generate_report(metrics):
    """Print a summary report."""
    active_count = sum(1 for m in metrics if m["status"] == "active")
    total = len(metrics)
    avg_dur = sum(m["avg_session_duration"] for m in metrics) / total
    print(f"Report: {active_count}/{total} users active")
    print(f"Average session duration: {avg_dur:.1f} min")


def main():
    sample_data = json.dumps(
        [
            {"id": 1, "total_duration": 120, "sessions": 4, "is_active": True},
            {"id": 2, "total_duration": 0, "sessions": 0, "is_active": False},
            {"id": 3, "total_duration": 90, "sessions": 3, "is_active": True},
        ]
    )

    print("Starting user metrics job...")
    users = load_users(sample_data)
    metrics = calculate_metrics(users)
    generate_report(metrics)
    print("Job complete!")


if __name__ == "__main__":
    main()
