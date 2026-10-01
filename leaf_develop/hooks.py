# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "leaf_develop"
app_title = "Leaf Develop"
app_publisher = "Frappe"
app_description = "This app contain all modules of leaf"
app_icon = "octicon octicon-book"
app_color = "#589494"
app_email = "info@grintsys.com"
app_license = "GNU Genereal Public License"

override_whitelisted_methods = {
	"frappe.desk.moduleview.get": "leaf_develop.moduleview.get_accounts_module_data",
	"frappe.desk.query_report.get_script": "leaf_develop.query_report_overrides.get_script",
	"frappe.desk.query_report.run": "leaf_develop.query_report_overrides.run",
	"frappe.desk.query_report.export_query": "leaf_develop.query_report_overrides.export_query"
}

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/leaf_develop/css/leaf_develop.css"
# app_include_js = "/assets/leaf_develop/js/leaf_develop.js"

# include js, css files in header of web template
# web_include_css = "/assets/leaf_develop/css/leaf_develop.css"
# web_include_js = "/assets/leaf_develop/js/leaf_develop.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "leaf_develop.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "leaf_develop.install.before_install"
# after_install = "leaf_develop.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "leaf_develop.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"leaf_develop.tasks.all"
# 	],
# 	"daily": [
# 		"leaf_develop.tasks.daily"
# 	],
# 	"hourly": [
# 		"leaf_develop.tasks.hourly"
# 	],
# 	"weekly": [
# 		"leaf_develop.tasks.weekly"
# 	]
# 	"monthly": [
# 		"leaf_develop.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "leaf_develop.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "leaf_develop.event.get_events"
# }

