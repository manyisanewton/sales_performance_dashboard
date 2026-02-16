# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company
# For license information, please see license.txt

"""
Personal Sales Dashboard
Contains all metrics and queries for individual sales representative dashboard
"""

import frappe
from frappe import _
from frappe.utils import (
    getdate, 
    nowdate, 
    get_first_day, 
    get_last_day,
    add_to_date,
    flt
)
from datetime import timedelta
from typing import Dict, Any, Optional, List

class PersonalSalesDashboard:
    """Handler class for Personal Sales Dashboard metrics"""
    
    def __init__(self, user: Optional[str] = None):
        """
        Initialize dashboard with user context
        
        Args:
            user: User email, defaults to current session user
        """
        self.user = user or frappe.session.user
        self.today = getdate(nowdate())
        self.demo_pattern = "%DEMO%"
        
        # Month boundaries
        self.month_start = get_first_day(self.today)
        self.month_end = get_last_day(self.today)
        
        # Week boundaries (Monday to Sunday)
        self.week_start = self.today - timedelta(days=self.today.weekday())
        self.week_end = self.week_start + timedelta(days=6)
        
        # Validate permissions
        self._validate_access()
    
    def _validate_access(self):
        """Validate user has appropriate permissions"""
        if frappe.session.user == "Guest":
            frappe.throw(_("Please login to access dashboard"), frappe.PermissionError)

    def _get_employee(self) -> Optional[str]:
        """Get Employee linked to current user."""
        return frappe.db.get_value("Employee", {"user_id": self.user}, "name")

    def _get_sales_persons(self) -> List[str]:
        """Get Sales Person records linked to current user."""
        employee = self._get_employee()
        if not employee:
            return []
        return frappe.get_all("Sales Person", filters={"employee": employee}, pluck="name")

    def _make_card_value(self, value, fieldtype="Currency"):
        """Return value in Number Card custom format."""
        return {"value": value, "fieldtype": fieldtype}

    def _route_to(self, doctype, route_options=None):
        """Return route metadata for a Number Card."""
        return {
            "route": ["List", doctype, "List"],
            "route_options": route_options or {},
        }

    def _is_not_demo_filter(self, fieldname: str):
        """Return a Not Like filter for demo records."""
        return [fieldname, "not like", self.demo_pattern]
    
    def get_cache_key(self, metric: str) -> str:
        """Generate cache key for metrics"""
        return f"personal_dashboard:{self.user}:{metric}:{self.today}"
    
    # ==================== Revenue Metrics ====================
    
    @frappe.whitelist()
    def get_total_revenue(self) -> float:
        """
        Get total revenue from submitted Sales Invoices for current month
        
        Returns:
            float: Total grand_total amount
        """
        cache_key = self.get_cache_key("revenue")
        cached_value = frappe.cache().get_value(cache_key)
        
        if cached_value is not None:
            return flt(cached_value)
        
        result = frappe.db.sql(
            """
            SELECT COALESCE(SUM(grand_total), 0) as value
            FROM `tabSales Invoice`
            WHERE docstatus = 1
                AND owner = %(user)s
                AND customer NOT LIKE %(demo)s
                AND posting_date BETWEEN %(from_date)s AND %(to_date)s
            """,
            {
                "user": self.user,
                "demo": self.demo_pattern,
                "from_date": self.month_start,
                "to_date": self.month_end,
            },
            as_dict=1,
        )
        
        value = flt(result[0].value) if result else 0.0
        
        # Cache for 5 minutes
        frappe.cache().set_value(cache_key, value, expires_in_sec=300)
        
        return value
    
    @frappe.whitelist()
    def get_total_collected(self) -> float:
        """
        Get total collected amount from Payment Entries for current month
        
        Returns:
            float: Total paid_amount
        """
        cache_key = self.get_cache_key("collected")
        cached_value = frappe.cache().get_value(cache_key)
        
        if cached_value is not None:
            return flt(cached_value)
        
        result = frappe.db.sql("""
            SELECT COALESCE(SUM(paid_amount), 0) as value
            FROM `tabPayment Entry`
            WHERE docstatus = 1
                AND owner = %(user)s
                AND party NOT LIKE %(demo)s
                AND posting_date BETWEEN %(from_date)s AND %(to_date)s
                AND payment_type = 'Receive'
        """, {
            'user': self.user,
            'demo': self.demo_pattern,
            'from_date': self.month_start,
            'to_date': self.month_end
        }, as_dict=1)
        
        value = flt(result[0].value) if result else 0.0
        frappe.cache().set_value(cache_key, value, expires_in_sec=300)
        
        return value
    
    @frappe.whitelist()
    def get_total_outstanding(self) -> float:
        """
        Get total outstanding amount from all Sales Invoices
        
        Returns:
            float: Total outstanding_amount
        """
        cache_key = self.get_cache_key("outstanding")
        cached_value = frappe.cache().get_value(cache_key)
        
        if cached_value is not None:
            return flt(cached_value)
        
        result = frappe.db.sql(
            """
            SELECT COALESCE(SUM(outstanding_amount), 0) as value
            FROM `tabSales Invoice`
            WHERE docstatus = 1
                AND owner = %(user)s
                AND outstanding_amount > 0
                AND customer NOT LIKE %(demo)s
            """,
            {"user": self.user, "demo": self.demo_pattern},
            as_dict=1,
        )
        
        value = flt(result[0].value) if result else 0.0
        frappe.cache().set_value(cache_key, value, expires_in_sec=300)
        
        return value
    
    # ==================== Target Metrics ====================
    
    @frappe.whitelist()
    def get_monthly_target(self) -> float:
        """
        Get monthly sales target from Sales Targets doctype
        
        Returns:
            float: Target amount for current month
        """
        cache_key = self.get_cache_key("target")
        cached_value = frappe.cache().get_value(cache_key)
        
        if cached_value is not None:
            return flt(cached_value)
        
        employee = self._get_employee()
        if not employee:
            return 0.0

        result = frappe.db.sql(
            """
            SELECT
                COALESCE(monthly_target_current, monthly_target, 0) as value
            FROM `tabSales Targets`
            WHERE target_level = 'Individual'
                AND employee = %(employee)s
                AND start_date <= %(today)s
                AND end_date >= %(today)s
                AND docstatus = 0
            ORDER BY modified DESC
            LIMIT 1
            """,
            {"employee": employee, "today": self.today},
            as_dict=1,
        )
        
        value = flt(result[0].value) if result else 0.0
        frappe.cache().set_value(cache_key, value, expires_in_sec=3600)  # Cache for 1 hour
        
        return value
    
    @frappe.whitelist()
    def get_target_percentage(self) -> float:
        """
        Calculate percentage achievement towards monthly target
        
        Returns:
            float: Percentage (0-100+)
        """
        revenue = self.get_total_revenue()
        target = self.get_monthly_target()
        
        if target <= 0:
            return 0.0
        
        return round((revenue / target) * 100, 2)
    
    # ==================== Lead & Opportunity Metrics ====================
    
    @frappe.whitelist()
    def get_total_leads(self) -> int:
        """
        Get total leads created in current month
        
        Returns:
            int: Count of leads
        """
        return frappe.db.count('Lead', {
            'owner': self.user,
            'name': ['not like', self.demo_pattern],
            'creation': ['between', [self.month_start, self.month_end]]
        })
    
    @frappe.whitelist()
    def get_total_opportunities(self) -> int:
        """
        Get total opportunities created in current month
        
        Returns:
            int: Count of opportunities
        """
        return frappe.db.count('Opportunity', {
            'owner': self.user,
            'name': ['not like', self.demo_pattern],
            'party_name': ['not like', self.demo_pattern],
            'creation': ['between', [self.month_start, self.month_end]]
        })
    
    @frappe.whitelist()
    def get_opportunities_value(self) -> float:
        """
        Get total value of opportunities in current month
        
        Returns:
            float: Sum of opportunity_amount
        """
        result = frappe.db.sql("""
            SELECT COALESCE(SUM(opportunity_amount), 0) as value
            FROM `tabOpportunity`
            WHERE owner = %(user)s
                AND name NOT LIKE %(demo)s
                AND party_name NOT LIKE %(demo)s
                AND creation BETWEEN %(from_date)s AND %(to_date)s
        """, {
            'user': self.user,
            'demo': self.demo_pattern,
            'from_date': self.month_start,
            'to_date': self.month_end
        }, as_dict=1)
        
        return flt(result[0].value) if result else 0.0
    
    @frappe.whitelist()
    def get_won_deals(self) -> int:
        """
        Get count of won opportunities in current month
        
        Returns:
            int: Count of converted opportunities
        """
        return frappe.db.count('Opportunity', {
            'owner': self.user,
            'status': 'Converted',
            'name': ['not like', self.demo_pattern],
            'party_name': ['not like', self.demo_pattern],
            'modified': ['between', [self.month_start, self.month_end]]
        })
    
    @frappe.whitelist()
    def get_lost_deals(self) -> int:
        """
        Get count of lost opportunities in current month
        
        Returns:
            int: Count of lost opportunities
        """
        return frappe.db.count('Opportunity', {
            'owner': self.user,
            'status': 'Lost',
            'name': ['not like', self.demo_pattern],
            'party_name': ['not like', self.demo_pattern],
            'modified': ['between', [self.month_start, self.month_end]]
        })

    @frappe.whitelist()
    def get_ongoing_deals(self) -> int:
        """
        Get count of ongoing opportunities (not Lost/Converted) in current month
        """
        return frappe.db.count('Opportunity', {
            'owner': self.user,
            'status': ['not in', ['Converted', 'Lost']],
            'name': ['not like', self.demo_pattern],
            'party_name': ['not like', self.demo_pattern],
            'creation': ['between', [self.month_start, self.month_end]]
        })

    @frappe.whitelist()
    def get_avg_deal_value(self) -> float:
        """
        Get average opportunity amount in current month
        """
        result = frappe.db.sql(
            """
            SELECT COALESCE(AVG(opportunity_amount), 0) as value
            FROM `tabOpportunity`
            WHERE owner = %(user)s
              AND name NOT LIKE %(demo)s
              AND party_name NOT LIKE %(demo)s
              AND creation BETWEEN %(from_date)s AND %(to_date)s
            """,
            {
                'user': self.user,
                'demo': self.demo_pattern,
                'from_date': self.month_start,
                'to_date': self.month_end
            },
            as_dict=1
        )
        return flt(result[0].value) if result else 0.0

    @frappe.whitelist()
    def get_avg_won_deal_value(self) -> float:
        """
        Get average value of converted opportunities in current month
        """
        result = frappe.db.sql(
            """
            SELECT COALESCE(AVG(opportunity_amount), 0) as value
            FROM `tabOpportunity`
            WHERE owner = %(user)s
              AND status = 'Converted'
              AND name NOT LIKE %(demo)s
              AND party_name NOT LIKE %(demo)s
              AND modified BETWEEN %(from_date)s AND %(to_date)s
            """,
            {
                'user': self.user,
                'demo': self.demo_pattern,
                'from_date': self.month_start,
                'to_date': self.month_end
            },
            as_dict=1
        )
        return flt(result[0].value) if result else 0.0

    @frappe.whitelist()
    def get_avg_time_to_close_deal(self) -> dict:
        """
        Average time (days) from opportunity creation to conversion in current month
        """
        rows = frappe.db.sql(
            """
            SELECT DATEDIFF(modified, creation) as days
            FROM `tabOpportunity`
            WHERE owner = %(user)s
              AND status = 'Converted'
              AND name NOT LIKE %(demo)s
              AND party_name NOT LIKE %(demo)s
              AND modified BETWEEN %(from_date)s AND %(to_date)s
            """,
            {
                'user': self.user,
                'demo': self.demo_pattern,
                'from_date': self.month_start,
                'to_date': self.month_end
            },
            as_dict=1
        )
        if not rows:
            return self._make_card_value("0 days", "Data")
        avg_days = sum((r.days or 0) for r in rows) / max(len(rows), 1)
        return self._make_card_value(f"{round(avg_days)} days", "Data")

    @frappe.whitelist()
    def get_avg_time_lead_to_deal(self) -> dict:
        """
        Average time (days) from lead creation to converted opportunity in current month
        """
        rows = frappe.db.sql(
            """
            SELECT DATEDIFF(o.modified, l.creation) as days
            FROM `tabOpportunity` o
            INNER JOIN `tabLead` l ON l.name = o.party_name
            WHERE o.owner = %(user)s
              AND o.opportunity_from = 'Lead'
              AND o.status = 'Converted'
              AND o.name NOT LIKE %(demo)s
              AND o.party_name NOT LIKE %(demo)s
              AND l.name NOT LIKE %(demo)s
              AND o.modified BETWEEN %(from_date)s AND %(to_date)s
            """,
            {
                'user': self.user,
                'demo': self.demo_pattern,
                'from_date': self.month_start,
                'to_date': self.month_end
            },
            as_dict=1
        )
        if not rows:
            return self._make_card_value("0 days", "Data")
        avg_days = sum((r.days or 0) for r in rows) / max(len(rows), 1)
        return self._make_card_value(f"{round(avg_days)} days", "Data")
    
    # ==================== Customer Metrics ====================
    
    @frappe.whitelist()
    def get_new_customers_week(self) -> int:
        """
        Get new customers created this week
        
        Returns:
            int: Count of new customers
        """
        return frappe.db.count('Customer', {
            'owner': self.user,
            'name': ['not like', self.demo_pattern],
            'customer_name': ['not like', self.demo_pattern],
            'creation': ['between', [self.week_start, self.week_end]]
        })
    
    @frappe.whitelist()
    def get_new_customers_month(self) -> int:
        """
        Get new customers created this month
        
        Returns:
            int: Count of new customers
        """
        return frappe.db.count('Customer', {
            'owner': self.user,
            'name': ['not like', self.demo_pattern],
            'customer_name': ['not like', self.demo_pattern],
            'creation': ['between', [self.month_start, self.month_end]]
        })
    
    @frappe.whitelist()
    def get_customers_served_week(self) -> int:
        """
        Get unique customers served this week (from Sales Invoices)
        
        Returns:
            int: Count of unique customers
        """
        result = frappe.db.sql(
            """
            SELECT COUNT(DISTINCT customer) as value
            FROM `tabSales Invoice`
            WHERE docstatus = 1
                AND owner = %(user)s
                AND customer NOT LIKE %(demo)s
                AND posting_date BETWEEN %(from_date)s AND %(to_date)s
            """,
            {
                "user": self.user,
                "demo": self.demo_pattern,
                "from_date": self.week_start,
                "to_date": self.week_end,
            },
            as_dict=1,
        )
        
        return int(result[0].value) if result else 0
    
    @frappe.whitelist()
    def get_customers_served_month(self) -> int:
        """
        Get unique customers served this month (from Sales Invoices)
        
        Returns:
            int: Count of unique customers
        """
        result = frappe.db.sql(
            """
            SELECT COUNT(DISTINCT customer) as value
            FROM `tabSales Invoice`
            WHERE docstatus = 1
                AND owner = %(user)s
                AND customer NOT LIKE %(demo)s
                AND posting_date BETWEEN %(from_date)s AND %(to_date)s
            """,
            {
                "user": self.user,
                "demo": self.demo_pattern,
                "from_date": self.month_start,
                "to_date": self.month_end,
            },
            as_dict=1,
        )
        
        return int(result[0].value) if result else 0
    
    # ==================== Appointment Metrics ====================
    
    @frappe.whitelist()
    def get_total_appointments(self) -> int:
        """
        Get total appointments scheduled this month
        Note: Returns 0 if Appointment doctype doesn't exist
        
        Returns:
            int: Count of appointments
        """
        if not frappe.db.exists('DocType', 'Appointment'):
            return 0
        
        return frappe.db.count('Appointment', {
            'owner': self.user,
            'scheduled_time': ['between', [self.month_start, self.month_end]]
        })
    
    @frappe.whitelist()
    def get_open_appointments(self) -> int:
        """
        Get currently open/scheduled appointments
        
        Returns:
            int: Count of open appointments
        """
        if not frappe.db.exists('DocType', 'Appointment'):
            return 0
        
        return frappe.db.count('Appointment', {
            'owner': self.user,
            'status': ['in', ['Open', 'Scheduled']]
        })
    
    @frappe.whitelist()
    def get_closed_appointments(self) -> int:
        """
        Get closed appointments this month
        
        Returns:
            int: Count of closed appointments
        """
        if not frappe.db.exists('DocType', 'Appointment'):
            return 0
        
        return frappe.db.count('Appointment', {
            'owner': self.user,
            'status': 'Closed',
            'scheduled_time': ['between', [self.month_start, self.month_end]]
        })
    
    # ==================== Invoice Metrics ====================
    
    @frappe.whitelist()
    def get_total_invoices(self) -> int:
        """
        Get total submitted sales invoices this month
        
        Returns:
            int: Count of sales invoices
        """
        return frappe.db.count(
            "Sales Invoice",
            {
                "owner": self.user,
                "docstatus": 1,
                "posting_date": ["between", [self.month_start, self.month_end]],
                "customer": ["not like", self.demo_pattern],
            },
        )
    
    # ==================== Aggregate Method ====================
    
    @frappe.whitelist()
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all dashboard metrics in a single call (for API efficiency)
        
        Returns:
            dict: All metrics in one dictionary
        """
        return {
            'revenue': self.get_total_revenue(),
            'collected': self.get_total_collected(),
            'outstanding': self.get_total_outstanding(),
            'target': self.get_monthly_target(),
            'target_percentage': self.get_target_percentage(),
            'leads': self.get_total_leads(),
            'opportunities': self.get_total_opportunities(),
            'opportunities_value': self.get_opportunities_value(),
            'new_customers_week': self.get_new_customers_week(),
            'new_customers_month': self.get_new_customers_month(),
            'appointments_total': self.get_total_appointments(),
            'appointments_open': self.get_open_appointments(),
            'appointments_closed': self.get_closed_appointments(),
            'customers_served_week': self.get_customers_served_week(),
            'customers_served_month': self.get_customers_served_month(),
            'won_deals': self.get_won_deals(),
            'lost_deals': self.get_lost_deals(),
            'total_invoices': self.get_total_invoices(),
        }


# ==================== Whitelisted API Methods ====================

@frappe.whitelist()
def get_personal_dashboard_metrics():
    """
    API endpoint to get all personal dashboard metrics
    
    Returns:
        dict: All dashboard metrics
    """
    dashboard = PersonalSalesDashboard()
    return dashboard.get_all_metrics()


# Individual metric endpoints (for Number Cards)

@frappe.whitelist()
def get_revenue():
    """API: Get total revenue"""
    dash = PersonalSalesDashboard()
    value = dash.get_total_revenue()
    return {
        **dash._make_card_value(value, "Currency"),
        **dash._route_to("Sales Invoice", {
            "posting_date": ["between", [dash.month_start, dash.month_end]],
            "docstatus": 1,
            "customer": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_collected():
    """API: Get total collected"""
    dash = PersonalSalesDashboard()
    value = dash.get_total_collected()
    return {
        **dash._make_card_value(value, "Currency"),
        **dash._route_to("Payment Entry", {
            "posting_date": ["between", [dash.month_start, dash.month_end]],
            "payment_type": "Receive",
            "docstatus": 1,
            "party": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_outstanding():
    """API: Get total outstanding"""
    dash = PersonalSalesDashboard()
    value = dash.get_total_outstanding()
    return {
        **dash._make_card_value(value, "Currency"),
        **dash._route_to("Sales Invoice", {
            "outstanding_amount": [">", 0],
            "docstatus": 1,
            "customer": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_target():
    """API: Get monthly target"""
    dash = PersonalSalesDashboard()
    value = dash.get_monthly_target()
    return {
        **dash._make_card_value(value, "Currency"),
        **dash._route_to("Sales Targets", {}),
    }

@frappe.whitelist()
def get_target_achievement():
    """API: Get target percentage"""
    dash = PersonalSalesDashboard()
    value = dash.get_target_percentage()
    return {
        **dash._make_card_value(value, "Percent"),
        **dash._route_to("Sales Targets", {}),
    }

@frappe.whitelist()
def get_leads():
    """API: Get total leads"""
    dash = PersonalSalesDashboard()
    value = dash.get_total_leads()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Lead", {
            "creation": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
            "name": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_opportunities():
    """API: Get total opportunities"""
    dash = PersonalSalesDashboard()
    value = dash.get_total_opportunities()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Opportunity", {
            "creation": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
            "name": ["not like", dash.demo_pattern],
            "party_name": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_opportunities_value():
    """API: Get opportunities value"""
    dash = PersonalSalesDashboard()
    value = dash.get_opportunities_value()
    return {
        **dash._make_card_value(value, "Currency"),
        **dash._route_to("Opportunity", {
            "creation": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
            "name": ["not like", dash.demo_pattern],
            "party_name": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_new_customers_week():
    """API: Get new customers this week"""
    dash = PersonalSalesDashboard()
    value = dash.get_new_customers_week()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Customer", {
            "creation": ["between", [dash.week_start, dash.week_end]],
            "owner": dash.user,
            "name": ["not like", dash.demo_pattern],
            "customer_name": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_new_customers_month():
    """API: Get new customers this month"""
    dash = PersonalSalesDashboard()
    value = dash.get_new_customers_month()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Customer", {
            "creation": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
            "name": ["not like", dash.demo_pattern],
            "customer_name": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_total_appointments():
    """API: Get total appointments"""
    dash = PersonalSalesDashboard()
    value = dash.get_total_appointments()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Appointment", {
            "scheduled_time": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
        }),
    }

@frappe.whitelist()
def get_open_appointments():
    """API: Get open appointments"""
    dash = PersonalSalesDashboard()
    value = dash.get_open_appointments()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Appointment", {
            "status": ["in", ["Open", "Scheduled"]],
            "owner": dash.user,
        }),
    }

@frappe.whitelist()
def get_closed_appointments():
    """API: Get closed appointments"""
    dash = PersonalSalesDashboard()
    value = dash.get_closed_appointments()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Appointment", {
            "status": "Closed",
            "scheduled_time": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
        }),
    }

@frappe.whitelist()
def get_customers_served_week():
    """API: Get customers served this week"""
    dash = PersonalSalesDashboard()
    value = dash.get_customers_served_week()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Sales Invoice", {
            "posting_date": ["between", [dash.week_start, dash.week_end]],
            "docstatus": 1,
            "customer": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_customers_served_month():
    """API: Get customers served this month"""
    dash = PersonalSalesDashboard()
    value = dash.get_customers_served_month()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Sales Invoice", {
            "posting_date": ["between", [dash.month_start, dash.month_end]],
            "docstatus": 1,
            "customer": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_won_deals():
    """API: Get won deals"""
    dash = PersonalSalesDashboard()
    value = dash.get_won_deals()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Opportunity", {
            "status": "Converted",
            "modified": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
            "name": ["not like", dash.demo_pattern],
            "party_name": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_lost_deals():
    """API: Get lost deals"""
    dash = PersonalSalesDashboard()
    value = dash.get_lost_deals()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Opportunity", {
            "status": "Lost",
            "modified": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
            "name": ["not like", dash.demo_pattern],
            "party_name": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_ongoing_deals():
    """API: Get ongoing deals"""
    dash = PersonalSalesDashboard()
    value = dash.get_ongoing_deals()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Opportunity", {
            "status": ["not in", ["Converted", "Lost"]],
            "creation": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
            "name": ["not like", dash.demo_pattern],
            "party_name": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_avg_deal_value():
    """API: Get average deal value"""
    dash = PersonalSalesDashboard()
    value = dash.get_avg_deal_value()
    return {
        **dash._make_card_value(value, "Currency"),
        **dash._route_to("Opportunity", {
            "creation": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
            "name": ["not like", dash.demo_pattern],
            "party_name": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_avg_won_deal_value():
    """API: Get average won deal value"""
    dash = PersonalSalesDashboard()
    value = dash.get_avg_won_deal_value()
    return {
        **dash._make_card_value(value, "Currency"),
        **dash._route_to("Opportunity", {
            "status": "Converted",
            "modified": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
            "name": ["not like", dash.demo_pattern],
            "party_name": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_avg_time_to_close_deal():
    """API: Get average time to close a deal"""
    dash = PersonalSalesDashboard()
    return {
        **dash.get_avg_time_to_close_deal(),
        **dash._route_to("Opportunity", {
            "status": "Converted",
            "modified": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
            "name": ["not like", dash.demo_pattern],
            "party_name": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_avg_time_lead_to_deal():
    """API: Get average time from lead to deal close"""
    dash = PersonalSalesDashboard()
    return {
        **dash.get_avg_time_lead_to_deal(),
        **dash._route_to("Opportunity", {
            "status": "Converted",
            "opportunity_from": "Lead",
            "modified": ["between", [dash.month_start, dash.month_end]],
            "owner": dash.user,
            "name": ["not like", dash.demo_pattern],
            "party_name": ["not like", dash.demo_pattern],
        }),
    }

@frappe.whitelist()
def get_total_invoices():
    """API: Get total invoices"""
    dash = PersonalSalesDashboard()
    value = dash.get_total_invoices()
    return {
        **dash._make_card_value(value, "Int"),
        **dash._route_to("Sales Invoice", {
            "posting_date": ["between", [dash.month_start, dash.month_end]],
            "docstatus": 1,
            "customer": ["not like", dash.demo_pattern],
        }),
    }
