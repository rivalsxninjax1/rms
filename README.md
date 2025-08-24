# RMS Backend

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Auth (JWT)
- Obtain token: POST /api/auth/token/ {"username","password"}
- Refresh: POST /api/auth/token/refresh/ {"refresh"}

### API
- Swagger UI: /api/docs/
- Schema: /api/schema/

### Menu Endpoints
- /api/menu/categories/
- /api/menu/items/

### Orders
- /api/orders/
- /api/orders/{id}/place/
```json
{
  "organization": "<org_uuid>",
  "location": "<loc_uuid>",
  "service_type": "DINE_IN",
  "items": [{
    "menu_item": 1,
    "name": "Margherita",
    "qty": "1",
    "unit_price": "9.99",
    "total": "9.99"
  }]
}
```
