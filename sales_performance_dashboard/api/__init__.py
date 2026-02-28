from .department_dashboard_api import (
    get_department_kpis,
    get_department_options,
    get_department_sales_target_route,
    get_department_top_customers_table,
)
from .personal_dashboard_api import get_my_sales_target_route, get_personal_dashboard_data

__all__ = [
    "get_personal_dashboard_data",
    "get_my_sales_target_route",
    "get_department_options",
    "get_department_sales_target_route",
    "get_department_kpis",
    "get_department_top_customers_table",
]
