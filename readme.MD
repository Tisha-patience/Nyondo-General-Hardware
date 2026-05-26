## Overview

Nyondo-General-Hardware is a Django application for a hardware store. It provides functionality for managing stock, sales, and suppliers.
It includes a dashboard for store managers and an attendant dashboard for sales attendants, both of which are accessible to authenticated users. The application also includes a login page for users to log in and a logout page for users to log out.
The system allows users to create, update, and delete stock, sales, and suppliers. Administrators can access the dashboard to manage stock, sales, and suppliers, while sales attendants can access their own dashboard to manage their sales and receipts.

## Features

- Dashboard for store managers to manage stock, sales, and suppliers.
- Attendant dashboard for sales attendants to manage their sales and receipts.
- Login page for users to log in.
- Logout page for users to log out.
- Create, update, and delete stock, sales, and suppliers are deactivated not deleted.
- Auto-update stock and totals when a SaleItem is added.
- Input validation (Ugandan National ID, phone number, non-negative numbers, non-empty fields).
- Reporting dashboards** for managers
- Secure authentication & registration via the user app
- Receipt number generation for sales
- Deposit tracking for participants

## System Architecture
- APPS
    - nyondogeneralhardwareapp  
    - user

- MODELS
    - Supplier
    - Stock 
    - Sale
    - SaleItem
    - SaleReceipt
    - Deposit
    - DepositReceipt
    - GoodsCollection
    - GoodsReceipt
    - Participant

- VIEWS
    -Login / Logout Views  
> Handle user authentication and session management.

- Attendant Dashboard (attendant_dashboard)  
> Allows attendants to record sales, generate receipts, and view their transactions.

- Manager Dashboard (manager_dashboard)  
> Displays stock levels, profit margins, and reporting features for managers.

- Admin Views  
>Provide full CRUD operations for stock, suppliers, and sales.

>Create, update, deactivate (not delete) stock and suppliers

>Manage users and assign roles

>Sales Registration (sales_reg)  
>Validates inputs, records sales, and automatically reduces stock quantities.

- Receipt Views (SaleReceipt, DepositReceipt, GoodsReceipt)  
>Generate and display receipts linked to transactions.

- Participant Views  
>Manage participant registration, deposits, and goods collection.

## Validation
- Custom validators for Ugandan phone numbers and national IDs.

- Error messages guide users to correct invalid inputs.

- Ensures data integrity and improves security.

## Requirements

- Django==6.0.5
- reportlab==4.5.1
- pillow==12.2.0

## Installation

To install Nyondo-General-Hardware, run the following command:

```bash
pip install Nyondo-General-Hardware
```

## Usage

To use Nyondo-General-Hardware, start the Django development server and navigate to the home page at http://localhost:8000/.

## Future Improvements
- Deploy to Heroku/PythonAnywhere
- Add analytics dashboards
- Improve UI/UX
- Integrate cloud storage

## Challenges & Solutions
- Validation difficulties → Solved with Django custom validators.

- Template loading errors → Fixed by restructuring directories.

- Stock reduction logic → Implemented by linking models and adding business rules.

- Receipt generation → Automated with unique ID logic in SaleReceipt.