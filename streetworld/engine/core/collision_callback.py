from streetworld.constants import MetaDriveType


def collision_callback(contact):
    node0 = contact.getNode0()
    node1 = contact.getNode1()

    nodes = [node0, node1]
    another_nodes = [node1, node0]
    for vehicle_node, another_node in zip(nodes, another_nodes):
        if not vehicle_node.hasPythonTag(MetaDriveType.VEHICLE):
            continue

        another_type = another_node.getName()
        if another_type in [MetaDriveType.BOUNDARY_SIDEWALK, MetaDriveType.CROSSWALK] \
                or MetaDriveType.is_road_line(another_type):
            continue

        vehicle = vehicle_node.getPythonTag(MetaDriveType.VEHICLE).base_object
        vehicle.contact_results.add(another_type)

        if another_type == MetaDriveType.VEHICLE:
            vehicle.crash_vehicle = True
        elif another_type in [MetaDriveType.CYCLIST, MetaDriveType.PEDESTRIAN]:
            vehicle.crash_human = True
        elif MetaDriveType.is_traffic_object(another_type):
            vehicle.crash_object = True
