def compute_constituent_fractions(model, constituent_set, associated_elements, unit_scale_to_mm):
    """
    Computes fractions for each material constituent based on their widths. Uses width as a fallback.

    Parameters:
    - model: The opened IfcOpenShell IFC model.
    - constituent_set: The IfcMaterialConstituentSet instance.
    - associated_elements: List of elements associated with the constituent set.
    - unit_scale_to_mm: Scaling factor to convert lengths to millimeters.

    Returns:
    - A tuple of (fractions, widths) where:
      - fractions: Dictionary mapping each constituent to its fraction
      - widths: Dictionary mapping each constituent to its width in mm
    """
    fractions = {}
    constituents = constituent_set.MaterialConstituents or []
    if not constituents:
        return fractions, {}  # No constituents to process

    # Collect quantities associated with the elements
    quantities = []
    for element in associated_elements:
        for rel in getattr(element, 'IsDefinedBy', []):
            if rel.is_a('IfcRelDefinesByProperties'):
                prop_def = rel.RelatingPropertyDefinition
                if prop_def.is_a('IfcElementQuantity'):
                    quantities.extend(prop_def.Quantities)

    # Build a mapping of quantity names to quantities
    quantity_name_map = {}
    for q in quantities:
        if q.is_a('IfcPhysicalComplexQuantity'):
            q_name = (q.Name or '').strip().lower()
            quantity_name_map.setdefault(q_name, []).append(q)

    # Handle constituents with duplicate names by order of appearance
    constituent_indices = {}
    constituent_widths = {}
    total_width_mm = 0.0

    for constituent in constituents:
        constituent_name = (constituent.Name or "Unnamed Constituent").strip().lower()
        count = constituent_indices.get(constituent_name, 0)
        constituent_indices[constituent_name] = count + 1

        width_mm = 0.0
        quantities_with_name = quantity_name_map.get(constituent_name, [])

        if count < len(quantities_with_name):
            matched_quantity = quantities_with_name[count]
            # Extract 'Width' sub-quantity
            for sub_q in getattr(matched_quantity, 'HasQuantities', []):
                if sub_q.is_a('IfcQuantityLength') and (sub_q.Name or '').strip().lower() == 'width':
                    raw_length_value = getattr(sub_q, 'LengthValue', 0.0)
                    width_mm = raw_length_value * unit_scale_to_mm
                    break

        constituent_widths[constituent] = width_mm
        total_width_mm += width_mm

    if total_width_mm == 0.0:
        # Assign equal fractions if total width is zero
        fractions = {constituent: 1.0 / len(constituents) for constituent in constituents}
    else:
        fractions = {constituent: (width_mm / total_width_mm) for constituent, width_mm in constituent_widths.items()}

    return fractions, constituent_widths