import bpy, json, os, traceback

class UpstreamTools:

    @staticmethod
    def _describe_property(prop):
        entry = {'identifier': prop.identifier, 'name': prop.name, 'type': prop.type, 'description': prop.description}
        for attr in ('is_required', 'is_readonly', 'is_argument_optional', 'array_length'):
            value = getattr(prop, attr, None)
            if value is not None:
                entry[attr] = value
        if prop.type == 'ENUM':
            try:
                entry['enum_items'] = [item.identifier for item in prop.enum_items]
            except Exception:
                pass
            try:
                entry['default'] = prop.default
            except Exception:
                pass
        elif prop.type in ('FLOAT', 'INT'):
            try:
                entry['default'] = list(prop.default_array) if getattr(prop, 'array_length', 0) else prop.default
            except Exception:
                pass
            for attr in ('hard_min', 'hard_max', 'soft_min', 'soft_max', 'subtype', 'unit', 'step'):
                value = getattr(prop, attr, None)
                if value is not None:
                    entry[attr] = value
        elif prop.type == 'BOOLEAN':
            try:
                entry['default'] = prop.default
            except Exception:
                pass
        elif prop.type == 'STRING':
            try:
                entry['default'] = prop.default
            except Exception:
                pass
            max_length = getattr(prop, 'max_length', None)
            if max_length:
                entry['max_length'] = max_length
        elif prop.type == 'POINTER':
            fixed_type = getattr(prop, 'fixed_type', None)
            if fixed_type is not None:
                entry['pointer_type'] = fixed_type.identifier
        elif prop.type == 'COLLECTION':
            fixed_type = getattr(prop, 'fixed_type', None)
            if fixed_type is not None:
                entry['collection_type'] = fixed_type.identifier
        return entry

    def describe_node_type(self, bl_idname, property_overrides=None):
        node_cls = getattr(bpy.types, bl_idname, None)
        if node_cls is None or not (isinstance(node_cls, type) and issubclass(node_cls, bpy.types.Node)):
            candidates = [name for name in dir(bpy.types) if 'Node' in name and bl_idname.lower() in name.lower()]
            return {'error': f'Unknown node type: {bl_idname}', 'did_you_mean': sorted(candidates)[:15]}
        tree_type_candidates = ['ShaderNodeTree', 'GeometryNodeTree', 'CompositorNodeTree', 'TextureNodeTree']
        node = None
        tree = None
        used_tree_type = None
        attempts = []
        for tree_type in tree_type_candidates:
            tmp_tree = None
            try:
                tmp_tree = bpy.data.node_groups.new(name='__mcp_introspect_tmp__', type=tree_type)
                node = tmp_tree.nodes.new(type=bl_idname)
                tree = tmp_tree
                used_tree_type = tree_type
                break
            except Exception as e:
                attempts.append(f'{tree_type}: {e}')
                if tmp_tree is not None:
                    try:
                        bpy.data.node_groups.remove(tmp_tree)
                    except Exception:
                        pass
        if node is None:
            return {'error': f"Could not instantiate node '{bl_idname}' in any node tree type", 'attempts': attempts}
        try:
            warnings = []
            if property_overrides:
                for key, value in property_overrides.items():
                    try:
                        setattr(node, key, value)
                    except Exception as e:
                        warnings.append(f"Could not set property '{key}' = {value!r}: {e}")
            base_props = set(bpy.types.Node.bl_rna.properties.keys())
            properties = [self._describe_property(prop) for prop in node.bl_rna.properties if prop.identifier not in base_props]

            def describe_sockets(sockets):
                out = []
                for index, socket in enumerate(sockets):
                    entry = {'index': index, 'identifier': socket.identifier, 'name': socket.name, 'type': socket.type, 'is_multi_input': getattr(socket, 'is_multi_input', False), 'hide_value': getattr(socket, 'hide_value', False), 'is_linked': socket.is_linked}
                    if hasattr(socket, 'default_value'):
                        try:
                            default_value = socket.default_value
                            if hasattr(default_value, '__len__') and (not isinstance(default_value, str)):
                                entry['default_value'] = list(default_value)
                            else:
                                entry['default_value'] = default_value
                        except Exception:
                            pass
                    out.append(entry)
                return out
            result = {'bl_idname': bl_idname, 'label': node.bl_label, 'instantiated_in': used_tree_type, 'properties': properties, 'inputs': describe_sockets(node.inputs), 'outputs': describe_sockets(node.outputs), 'applied_property_overrides': property_overrides or {}, 'note': "Sockets reflect the node's current property values (after any property_overrides applied above). Enum/mode-like properties (e.g. data_type, blend_type) can add, remove or reorder sockets - pass the mode you intend to use via property_overrides to see the real layout before writing code that indexes these sockets."}
            if warnings:
                result['warnings'] = warnings
            return result
        finally:
            try:
                bpy.data.node_groups.remove(tree)
            except Exception:
                pass

    def bpy_api_lookup(self, query):
        query = (query or '').strip()
        if not query:
            return {'error': 'Empty query'}
        q = query[4:] if query.startswith('bpy.') else query
        if q.startswith('ops.'):
            op_parts = q[len('ops.'):].split('.')
            op_parts = [p.split('(')[0] for p in op_parts if p]
            if len(op_parts) < 2:
                return {'error': f'Incomplete operator path: bpy.{q}. Expected bpy.ops.<category>.<name>'}
            category, op_name = (op_parts[0], op_parts[1])
            op_group = getattr(bpy.ops, category, None)
            op = getattr(op_group, op_name, None) if op_group is not None else None
            if op is None:
                return {'error': f'Unknown operator: bpy.ops.{category}.{op_name}'}
            try:
                rna = op.get_rna_type()
            except Exception as e:
                return {'error': f'Could not introspect operator bpy.ops.{category}.{op_name}: {e}'}
            parameters = [self._describe_property(prop) for prop in rna.properties if prop.identifier != 'rna_type']
            return {'kind': 'operator', 'idname': f'bpy.ops.{category}.{op_name}', 'label': rna.name, 'description': rna.description, 'parameters': parameters}
        parts = [p for p in q.split('.') if p and p != 'types']
        if not parts:
            return {'error': 'Empty query'}
        type_name = parts[0]
        node_cls = getattr(bpy.types, type_name, None)
        if node_cls is None:
            matches = sorted((name for name in dir(bpy.types) if type_name.lower() in name.lower()))
            return {'error': f'Unknown type: {type_name}', 'did_you_mean': matches[:15]}
        if len(parts) == 1:
            properties = [self._describe_property(prop) for prop in node_cls.bl_rna.properties if prop.identifier != 'rna_type']
            functions = []
            for func in node_cls.bl_rna.functions:
                functions.append({'identifier': func.identifier, 'description': func.description, 'parameters': [self._describe_property(p) for p in func.parameters if not p.is_output], 'returns': [self._describe_property(p) for p in func.parameters if p.is_output]})
            return {'kind': 'type', 'bl_idname': type_name, 'description': node_cls.bl_rna.description, 'properties': properties, 'functions': functions}
        member_name = parts[1]
        prop = node_cls.bl_rna.properties.get(member_name)
        if prop is not None:
            entry = self._describe_property(prop)
            entry['kind'] = 'property'
            entry['owner_type'] = type_name
            return entry
        func = node_cls.bl_rna.functions.get(member_name)
        if func is not None:
            return {'kind': 'function', 'owner_type': type_name, 'identifier': func.identifier, 'description': func.description, 'parameters': [self._describe_property(p) for p in func.parameters if not p.is_output], 'returns': [self._describe_property(p) for p in func.parameters if p.is_output]}
        available = sorted(list(node_cls.bl_rna.properties.keys()) + list(node_cls.bl_rna.functions.keys()))
        return {'error': f"'{type_name}' has no property or function named '{member_name}'", 'did_you_mean': [name for name in available if member_name.lower() in name.lower()][:15]}

    def export_scene(self, filepath, format='glb', object_names=None, selection_only=False, apply_modifiers=True):
        if not filepath:
            return {'error': 'filepath is required'}
        fmt = (format or 'glb').lower()
        if fmt not in ('glb', 'fbx'):
            return {'error': f"format must be glb or fbx, got '{format}'"}
        names = [n for n in object_names or [] if n]
        use_selection = False
        exported = []
        if names:
            missing = [n for n in names if bpy.data.objects.get(n) is None]
            if missing:
                return {'error': 'Objects not found in Blender: ' + ', '.join(missing)}
            bpy.ops.object.select_all(action='DESELECT')
            for n in names:
                obj = bpy.data.objects[n]
                for o in [obj, *obj.children_recursive]:
                    o.select_set(True)
                    if o.name not in exported:
                        exported.append(o.name)
            bpy.context.view_layer.objects.active = bpy.data.objects[names[0]]
            use_selection = True
        elif selection_only:
            if not bpy.context.selected_objects:
                return {'error': 'Nothing is selected in Blender and no object_names were given'}
            exported = [o.name for o in bpy.context.selected_objects]
            use_selection = True
        else:
            exported = [o.name for o in bpy.context.scene.objects]
        try:
            if bpy.context.object and getattr(bpy.context.object, 'mode', 'OBJECT') != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
        directory = os.path.dirname(filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if fmt == 'glb':
            bpy.ops.export_scene.gltf(filepath=filepath, export_format='GLB', use_selection=use_selection, use_active_scene=True, export_apply=apply_modifiers, export_animations=True, export_skins=True, export_morph=True, export_yup=True)
        else:
            bpy.ops.export_scene.fbx(filepath=filepath, use_selection=use_selection, apply_unit_scale=True, bake_space_transform=apply_modifiers, use_mesh_modifiers=apply_modifiers, path_mode='COPY', embed_textures=True)
        return {'path': filepath, 'bytes': os.path.getsize(filepath), 'selection_only': use_selection, 'exported': exported}
