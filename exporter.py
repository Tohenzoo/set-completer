import xml.etree.ElementTree as ET
from xml.dom import minidom

def generate_bricklink_xml(missing_parts, output_filepath):
    """
    Формирует корректный XML-файл Wanted List для BrickLink.
    missing_parts: список кортежей (part_num, color_id, quantity_missing)
    """
    inventory = ET.Element("INVENTORY")

    for part_num, color_id, qty in missing_parts:
        if qty <= 0:
            continue
        
        item = ET.SubElement(inventory, "ITEM")
        
        itemtype = ET.SubElement(item, "ITEMTYPE")
        itemtype.text = "P"  # P = Part (Деталь)
        
        itemid = ET.SubElement(item, "ITEMID")
        itemid.text = str(part_num)
        
        color = ET.SubElement(item, "COLOR")
        color.text = str(color_id)
        
        qty_elem = ET.SubElement(item, "MINQTY")
        qty_elem.text = str(qty)

    xml_str = ET.tostring(inventory, encoding="utf-8")
    parsed_xml = minidom.parseString(xml_str)
    pretty_xml = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")

    with open(output_filepath, "wb") as f:
        f.write(pretty_xml)
        
    return True