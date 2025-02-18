import sys
from collections import defaultdict
from urllib.request import urlopen
from proto.rocktree_pb2 import BulkMetadata
from proto.rocktree_pb2 import PlanetoidMetadata

from octant_to_latlong import octant_to_latlong
from octant_to_latlong import LatLonBox

PLANET = "earth"
URL_PREFIX = f"https://kh.google.com/rt/{PLANET}/"


def urlread(url):
    with urlopen(url) as f:
        return f.read()


def read_planetoid_metadata():
    url = URL_PREFIX + "PlanetoidMetadata"
    metadata = PlanetoidMetadata()
    metadata.ParseFromString(urlread(url))
    return metadata


def read_bulk_metadata(path, epoch):
    url = URL_PREFIX + f"BulkMetadata/pb=!1m2!1s{path}!2u{epoch}"
    metadata = BulkMetadata()
    metadata.ParseFromString(urlread(url))
    return metadata


def parse_path_and_flags(data):
    def split_bits(x, n):
        mask = (1 << n) - 1
        return x >> n, x & mask

    data, level = split_bits(data, 2)

    path_segments = list()
    for _ in range(level + 1):
        data, x = split_bits(data, 3)
        path_segments.append(x)

    path = "".join(str(x) for x in path_segments)
    return path, data


class NodeData(object):
    def __init__(self, bulk_path, path_and_flags):
        path, flags = parse_path_and_flags(path_and_flags)
        self.path = bulk_path + path
        self.flags = flags
        self.level = len(self.path)
        self.bbox = octant_to_latlong(self.path)

    def is_bulk(self):
        return (len(self.path) % 4 == 0) and (not (self.flags & 4))

    def is_overlap(self, bbox):
        return LatLonBox.is_overlapping(self.bbox, bbox)


def find_overlaps(bbox, max_octants_per_level):
    planetoid_metadata = read_planetoid_metadata()
    epoch = planetoid_metadata.root_node_metadata.epoch

    overlapping_octants = defaultdict(list)

    def update_overlapping_octants(path):
        bulk = read_bulk_metadata(path, epoch)
        bulk_path = bulk.head_node_key.path
        for node in bulk.node_metadata:
            node = NodeData(bulk_path, node.path_and_flags)
            if node.is_overlap(bbox):
                overlapping_octants[node.level].append(node)

    update_overlapping_octants("")
    for level in range(1, 21):
        # print("len = %s level = %s" % (len(overlapping_octants[level]), level))
        if len(overlapping_octants[level]) >= max_octants_per_level:
            break
        for octant in overlapping_octants[level]:
            if octant.is_bulk():
                update_overlapping_octants(octant.path)

    return overlapping_octants


def args_to_bbox(args):
    args = [float(x.rstrip(",")) for x in args]
    bottom, top = sorted([args[0], args[2]])
    left, right = sorted([args[1], args[3]])
    return LatLonBox(north=top, south=bottom, west=left, east=right)


if __name__ == "__main__":
    bbox = args_to_bbox(sys.argv[1:5])
    print(bbox)

    overlapping_octants = find_overlaps(bbox, 1000)
    data = ""
    for level in sorted(overlapping_octants):
        # print(f"[Octant level {level}]")
        data = data + "[Octant level " + str(level) + "]\n"
        for octant in overlapping_octants[level]:
            print(octant.path)
            data = data + octant.path + "\n"
    f = open(("octants_%s.txt" % ('-'.join(sys.argv[1:5]))), "a")
    f.write(data)
    f.close()
