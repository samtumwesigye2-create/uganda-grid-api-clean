from pathlib import Path


def patch_main():
    p = Path('main.py')
    s = p.read_text(encoding='utf-8')
    if 'from postal_assignment import resolve_zip' not in s:
        anchor = 'import xml.etree.ElementTree as ET\n'
        if anchor not in s:
            raise SystemExit('main.py import anchor not found')
        s = s.replace(anchor, anchor + 'from postal_assignment import resolve_zip\n', 1)

    old = 'updated = addresses + [{"grid_id": grid_id, "address": address, "latitude": sub["lat"], "longitude": sub["lon"], "address_type": "residential"}]'
    new = '''postal = resolve_zip(sub["lat"], sub["lon"])
    new_record = {"grid_id": grid_id, "address": address, "latitude": sub["lat"], "longitude": sub["lon"], "address_type": "residential"}
    if postal:
        new_record["zip_code"] = postal["zip_code"]
        new_record["postal_region"] = postal["region"]
        new_record["postal_zone"] = postal.get("name", "")
        sub["assigned_zip_code"] = postal["zip_code"]
    updated = addresses + [new_record]'''
    if old in s:
        s = s.replace(old, new, 1)
    elif 'new_record["zip_code"] = postal["zip_code"]' not in s:
        raise SystemExit('main.py residential approval anchor not found')
    p.write_text(s, encoding='utf-8')


def patch_commercial():
    p = Path('commercial.py')
    s = p.read_text(encoding='utf-8')
    if 'from postal_assignment import resolve_zip' not in s:
        anchor = 'from fastapi import APIRouter, Form, Header, HTTPException, Query, UploadFile, File\n'
        if anchor not in s:
            raise SystemExit('commercial.py import anchor not found')
        s = s.replace(anchor, anchor + 'from postal_assignment import resolve_zip\n', 1)

    old = '''        addresses = addresses_ref()
        addresses.append({
            "grid_id": grid_id,
            "address": row["address_text"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "address_type": "commercial",
            "is_master": True,
            "building_name": row["building_name"],
            "company_name": row["company_name"],
            "units": unit_list,
        })'''
    new = '''        addresses = addresses_ref()
        postal = resolve_zip(row["latitude"], row["longitude"])
        new_record = {
            "grid_id": grid_id,
            "address": row["address_text"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "address_type": "commercial",
            "is_master": True,
            "building_name": row["building_name"],
            "company_name": row["company_name"],
            "units": unit_list,
        }
        if postal:
            new_record["zip_code"] = postal["zip_code"]
            new_record["postal_region"] = postal["region"]
            new_record["postal_zone"] = postal.get("name", "")
        addresses.append(new_record)'''
    if old in s:
        s = s.replace(old, new, 1)
    elif 'new_record["postal_region"] = postal["region"]' not in s:
        raise SystemExit('commercial.py approval anchor not found')

    old_return = 'return {"id": application_id, "status": "approved", "grid_id": grid_id, "units": unit_list}'
    new_return = 'return {"id": application_id, "status": "approved", "grid_id": grid_id, "zip_code": postal["zip_code"] if postal else "", "units": unit_list}'
    if old_return in s:
        s = s.replace(old_return, new_return, 1)
    p.write_text(s, encoding='utf-8')


patch_main()
patch_commercial()
