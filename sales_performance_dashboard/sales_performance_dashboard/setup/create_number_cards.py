# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company
# For license information, please see license.txt

"""
Script to create all Personal Sales Dashboard Number Cards
Run: bench execute sales_performance_dashboard.sales_performance_dashboard.setup.create_number_cards.create_all_cards
"""

import frappe
from frappe import _

def create_all_cards():
    """Create all 16 number cards for Personal Sales Dashboard"""
    
    cards_config = [
        {
            'name': 'Personal - Total Revenue',
            'label': 'Total Revenue',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_revenue',
            'type': 'Custom',
            'color': 'Green',
            'is_public': 1,
        },
        {
            'name': 'Personal - Total Collected',
            'label': 'Total Collected',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_collected',
            'type': 'Custom',
            'color': 'Blue',
            'is_public': 1,
        },
        {
            'name': 'Personal - Total Outstanding',
            'label': 'Total Outstanding',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_outstanding',
            'type': 'Custom',
            'color': 'Orange',
            'is_public': 1,
        },
        {
            'name': 'Personal - Monthly Target',
            'label': 'Monthly Target',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_target',
            'type': 'Custom',
            'color': 'Purple',
            'is_public': 1,
        },
        {
            'name': 'Personal - Target Achievement',
            'label': '% Towards Target',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_target_achievement',
            'type': 'Custom',
            'color': 'Green',
            'is_public': 1,
        },
        {
            'name': 'Personal - Total Leads',
            'label': 'Total Leads',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_leads',
            'type': 'Custom',
            'color': 'Cyan',
            'is_public': 1,
        },
        {
            'name': 'Personal - Total Opportunities',
            'label': 'Total Opportunities',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_opportunities',
            'type': 'Custom',
            'color': 'Blue',
            'is_public': 1,
        },
        {
            'name': 'Personal - Opportunities Value',
            'label': 'Opportunities Value',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_opportunities_value',
            'type': 'Custom',
            'color': 'Purple',
            'is_public': 1,
        },
        {
            'name': 'Personal - New Customers Week',
            'label': 'New Customers (Week)',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_new_customers_week',
            'type': 'Custom',
            'color': 'Green',
            'is_public': 1,
        },
        {
            'name': 'Personal - New Customers Month',
            'label': 'New Customers (Month)',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_new_customers_month',
            'type': 'Custom',
            'color': 'Green',
            'is_public': 1,
        },
        {
            'name': 'Personal - Total Appointments',
            'label': 'Total Appointments',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_total_appointments',
            'type': 'Custom',
            'color': 'Orange',
            'is_public': 1,
        },
        {
            'name': 'Personal - Open Appointments',
            'label': 'Open Appointments',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_open_appointments',
            'type': 'Custom',
            'color': 'Yellow',
            'is_public': 1,
        },
        {
            'name': 'Personal - Closed Appointments',
            'label': 'Closed Appointments',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_closed_appointments',
            'type': 'Custom',
            'color': 'Gray',
            'is_public': 1,
        },
        {
            'name': 'Personal - Customers Served Week',
            'label': 'Customers Served (Week)',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_customers_served_week',
            'type': 'Custom',
            'color': 'Blue',
            'is_public': 1,
        },
        {
            'name': 'Personal - Customers Served Month',
            'label': 'Customers Served (Month)',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_customers_served_month',
            'type': 'Custom',
            'color': 'Blue',
            'is_public': 1,
        },
        {
            'name': 'Personal - Won Deals',
            'label': 'Won Deals',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_won_deals',
            'type': 'Custom',
            'color': 'Green',
            'is_public': 1,
        },
        {
            'name': 'Personal - Ongoing Deals',
            'label': 'Ongoing Deals',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_ongoing_deals',
            'type': 'Custom',
            'color': 'Blue',
            'is_public': 1,
        },
        {
            'name': 'Personal - Avg Deal Value',
            'label': 'Avg. Deal Value',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_avg_deal_value',
            'type': 'Custom',
            'color': 'Purple',
            'is_public': 1,
        },
        {
            'name': 'Personal - Avg Won Deal Value',
            'label': 'Avg. Won Deal Value',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_avg_won_deal_value',
            'type': 'Custom',
            'color': 'Green',
            'is_public': 1,
        },
        {
            'name': 'Personal - Avg Time to Close Deal',
            'label': 'Avg. Time to Close Deal',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_avg_time_to_close_deal',
            'type': 'Custom',
            'color': 'Gray',
            'is_public': 1,
        },
        {
            'name': 'Personal - Avg Time Lead to Deal',
            'label': 'Avg. Time Lead to Deal',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_avg_time_lead_to_deal',
            'type': 'Custom',
            'color': 'Gray',
            'is_public': 1,
        },
        {
            'name': 'Personal - Lost Deals',
            'label': 'Lost Deals',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_lost_deals',
            'type': 'Custom',
            'color': 'Red',
            'is_public': 1,
        },
        {
            'name': 'Personal - Total Invoices',
            'label': 'Total Invoices',
            'function': 'sales_performance_dashboard.sales_performance_dashboard.dashboards.personal_dashboard.get_total_invoices',
            'type': 'Custom',
            'color': 'Purple',
            'is_public': 1,
        }
    ]
    
    created_cards = []
    updated_cards = []
    
    for card_config in cards_config:
        card_name = card_config['name']
        
        # Check if card already exists
        if frappe.db.exists('Number Card', card_name):
            print(f"Updating existing card: {card_name}")
            card = frappe.get_doc('Number Card', card_name)
            updated_cards.append(card_name)
        else:
            print(f"Creating new card: {card_name}")
            card = frappe.new_doc('Number Card')
            card.name = card_name
            created_cards.append(card_name)
        
        
        card.label = card_config['label']
        card.method = card_config['function']
        card.type = card_config['type']
        card.color = card_config['color']
        card.is_public = card_config.get('is_public', 1)
        
        # Module and app reference
        card.module = 'Sales Performance Dashboard'
        card.document_type = ''  # Not linked to specific doctype
        
        # Save the card
        card.save(ignore_permissions=True)
        if card_config.get('description'):
            try:
                card.add_comment('Comment', card_config['description'])
            except Exception as e:
                print(f"  Warning: Could not add comment - {str(e)}")
    
    frappe.db.commit()
    
    print("\n" + "="*50)
    print(f"✅ Created {len(created_cards)} new Number Cards")
    print(f"🔄 Updated {len(updated_cards)} existing Number Cards")
    print("="*50)
    
    if created_cards:
        print("\nCreated Cards:")
        for card in created_cards:
            print(f"  - {card}")
    
    if updated_cards:
        print("\nUpdated Cards:")
        for card in updated_cards:
            print(f"  - {card}")
    
    return {
        'created': created_cards,
        'updated': updated_cards,
        'total': len(cards_config)
    }


def make_cards_public():
    """Force Personal number cards to be public."""
    updated = frappe.db.sql(
        """
        UPDATE `tabNumber Card`
        SET is_public = 1
        WHERE name LIKE 'Personal - %'
        """
    )
    frappe.db.commit()
    count = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabNumber Card` WHERE name LIKE 'Personal - %'",
        pluck=True,
    )[0]
    print(f"✅ Updated {count} cards to public.")


def debug_personal_cards():
    """Debug helper to list Personal cards from DB."""
    rows = frappe.db.sql(
        "SELECT name, is_public FROM `tabNumber Card` WHERE name LIKE '%Personal%' ORDER BY name",
        as_dict=True,
    )
    print("Found cards:", len(rows))
    for row in rows:
        print(row)
    return rows


def debug_any_cards(limit=10):
    """Debug helper to list any number cards from DB."""
    rows = frappe.db.sql(
        "SELECT name, is_public FROM `tabNumber Card` ORDER BY name LIMIT %s",
        limit,
        as_dict=True,
    )
    total = frappe.db.sql("SELECT COUNT(*) FROM `tabNumber Card`", pluck=True)[0]
    print("Total cards:", total)
    for row in rows:
        print(row)
    return rows


def debug_personal_methods():
    rows = frappe.db.sql(
        "SELECT name, label, method, is_public FROM `tabNumber Card` WHERE method LIKE 'sales_performance_dashboard.%' ORDER BY name",
        as_dict=True,
    )
    print("Found cards with personal methods:", len(rows))
    for row in rows:
        print(row)
    return rows


def normalize_personal_cards():
    """Normalize cards that use personal dashboard methods to be Custom + count fields."""
    rows = frappe.db.sql(
        """
        SELECT name, method
        FROM `tabNumber Card`
        WHERE method LIKE 'sales_performance_dashboard.%'
        """,
        as_dict=True,
    )
    for row in rows:
        doc = frappe.get_doc("Number Card", row["name"])
        doc.type = "Custom"
        doc.document_type = None
        doc.report_name = None
        doc.report_field = None
        doc.function = None
        doc.currency = None
        doc.is_public = 1
        doc.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"✅ Normalized {len(rows)} personal method cards.")


def delete_all_cards():
    """Delete all Personal Sales Dashboard Number Cards (use with caution)"""
    
    cards = frappe.get_all('Number Card', 
        filters={'name': ['like', 'Personal -%']},
        pluck='name'
    )
    
    for card_name in cards:
        frappe.delete_doc('Number Card', card_name, force=1)
    
    frappe.db.commit()
    
    print(f"🗑️ Deleted {len(cards)} Number Cards")
    return cards


def verify_cards():
    """Verify all cards are created and functional"""
    
    cards = frappe.get_all('Number Card',
        filters={'name': ['like', 'Personal -%']},
        fields=['name', 'label', 'function', 'type', 'color']
    )
    
    print("\n" + "="*50)
    print(f"Found {len(cards)} Personal Dashboard Number Cards")
    print("="*50 + "\n")
    
    for card in cards:
        print(f"📊 {card.label}")
        print(f"   Name: {card.name}")
        print(f"   Function: {card.function}")
        print(f"   Type: {card.type} | Color: {card.color}")
        print()
    
    return cards
