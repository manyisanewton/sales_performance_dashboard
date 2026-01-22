### Sales Performance Dashboard

Sales Performance Dashboard manages multi-level sales targets and live performance snapshots in ERPNext. The app supports Company, Department, and Individual targets, auto-calculates achievements from Sales Invoices, and applies carry-over logic across daily and monthly periods.

### Features

- Sales Targets DocType with Target Level, Company/Department/Employee selection, and target periods.
- Date-driven targets with Start/End Date required for each target.
- Auto-calculated achievements from Sales Invoices and Sales Team allocations.
- Carry-over for Daily and Monthly targets with over/under achievement (calendar days with holiday exclusions for daily).
- Current Target fields (Daily/Monthly/Quarterly/Yearly) computed against achievements to date.
- Progress fields for Yearly/Quarterly/Monthly/Weekly/Daily targets.
- Sales Performance Snapshot report with period-based performance (daily/weekly/monthly/quarterly/yearly).
- Company view shows all seven departments with totals; Department view shows employees with totals.
- Scheduled job refreshes achievements and current targets every minute.

### Key DocType: Sales Targets

Fields and behavior:

- Target Level: Company, Department, or Individual.
- Company/Department/Employee fields show based on Target Level.
- Target Period: Start Date and End Date.
- Base Targets: Yearly, Quarterly, Monthly (Company/Department); Weekly/Daily (Individual).
- Performance Summary: Total Achieved + current targets for Daily/Monthly/Quarterly/Yearly.
- Progress: Yearly/Quarterly/Monthly/Weekly/Daily percentages.

### Sales Performance Snapshot Report

Use `Sales Performance Snapshot` to view a point-in-time performance view for a chosen period:

- Periods: Daily, Weekly, Monthly, Quarterly, Yearly.
- Company view: lists the seven departments and includes a totals row.
- Department view: select a department to list employees and totals.

### Scheduled Refresh

A scheduled job recalculates achievements and progress every minute:

- `sales_performance_dashboard.tasks.update_sales_targets`

### Holiday Calendar

Daily carry-over excludes Sundays and uses the Holiday List:

- `Kenya Holiday list 2026`

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app sales_performance_dashboard
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/sales_performance_dashboard
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
