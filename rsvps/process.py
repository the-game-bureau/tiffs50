import os
import re
import email
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# Configuration: local folder for .eml files
FOLDER = r"C:\Code\temp"

# Output path remains in the script directory
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "rsvps.xml")


def extract_rsvp_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    submitted_line = soup.find(string=re.compile(r'^Submitted at'))

    rsvp_data = {}

    if table:
        for row in table.find_all('tr'):
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 2:
                key = cols[0].get_text(strip=True)
                value = cols[1].get_text(strip=True)
                if key and value:
                    rsvp_data[key] = value

    if submitted_line:
        rsvp_data['submitted_at'] = submitted_line.strip()

    return rsvp_data if rsvp_data else None


def get_existing_hashes_and_update_contacts(xml_path):
    """Load existing rsvps.xml, update <contact> fields to 'ON FILE', and return a set of their signature hashes."""
    existing_hashes = set()
    if not os.path.exists(xml_path):
        return existing_hashes

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Update all existing <contact> elements to ON FILE
    for rsvp in root.findall('rsvp'):
        contact_el = rsvp.find('contact')
        if contact_el is not None:
            contact_el.text = 'ON FILE'

    # Gather hashes after updating
    for rsvp in root.findall('rsvp'):
        data = {child.tag: (child.text or '').strip() for child in rsvp}
        rsvp_signature = tuple(sorted(data.items()))
        existing_hashes.add(rsvp_signature)

    # Write back updates for contact replacements
    ET.indent(tree, space="  ", level=0)
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)

    return existing_hashes


def process_emails_to_xml():
    # Ensure .eml folder exists
    if not os.path.isdir(FOLDER):
        print(f"⚠️ Folder not found: {FOLDER}")
        return

    # Load and update existing XML contacts, get existing signatures
    existing_hashes = get_existing_hashes_and_update_contacts(OUTPUT_PATH)

    new_rsvps = []
    new_hashes = set()

    for filename in os.listdir(FOLDER):
        if filename.lower().endswith('.eml'):
            filepath = os.path.join(FOLDER, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                msg = email.message_from_file(f)

                html = None
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == 'text/html':
                            html = part.get_payload(decode=True).decode(
                                part.get_content_charset() or 'utf-8', errors='replace'
                            )
                            break
                else:
                    if msg.get_content_type() == 'text/html':
                        html = msg.get_payload(decode=True).decode(
                            msg.get_content_charset() or 'utf-8', errors='replace'
                        )

                if html:
                    rsvp = extract_rsvp_from_html(html)
                    if rsvp:
                        # Override contact info for new RSVPs
                        if 'contact' in rsvp:
                            rsvp['contact'] = 'ON FILE'

                        rsvp_signature = tuple(sorted(rsvp.items()))
                        if rsvp_signature not in existing_hashes and rsvp_signature not in new_hashes:
                            new_hashes.add(rsvp_signature)
                            new_rsvps.append(rsvp)

    # Append new RSVPs to XML
    if os.path.exists(OUTPUT_PATH):
        tree = ET.parse(OUTPUT_PATH)
        root = tree.getroot()
    else:
        root = ET.Element("rsvps")
        tree = ET.ElementTree(root)

    for rsvp_data in new_rsvps:
        rsvp_el = ET.SubElement(root, "rsvp")
        for key, value in rsvp_data.items():
            child = ET.SubElement(rsvp_el, key)
            child.text = value

    ET.indent(tree, space="  ", level=0)
    tree.write(OUTPUT_PATH, encoding="utf-8", xml_declaration=True)
    print(f"✅ {len(new_rsvps)} new RSVP(s) added to {OUTPUT_PATH}")


if __name__ == "__main__":
    process_emails_to_xml()
