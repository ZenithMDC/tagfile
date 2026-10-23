from math import *

def dot_product(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def invert_angles(a):
    return [tau-a[0], tau-a[1], tau-a[2]]

def apply_rotation_to_points(points, angle, origin, verbose=False):
    o = origin
    a = angle[0]
    b = angle[1]
    c = angle[2]

    r = [cos(a)*cos(b), cos(a)*sin(b)*sin(c) - sin(a)*(cos(c)), cos(a)*sin(b)*cos(c) + sin(a)*sin(c),
         sin(a)*cos(b), sin(a)*sin(b)*sin(c) + cos(a)*cos(c),   sin(a)*sin(b)*cos(c) - cos(a)*sin(c),
         -sin(b),       cos(b)*sin(c),                          cos(b)*cos(c)                        ]

    rotated_points = []
    for i, p in enumerate(points):
        t = [p[0]-o[0], p[1]-o[1], p[2]-o[2]]

        th = dot_product(t, [r[0], r[1], r[2]])
        tp = dot_product(t, [r[3], r[4], r[5]])
        tb = dot_product(t, [r[6], r[7], r[8]])

        rotated_points.append([o[0]+th, o[1]+tp, o[2]+tb])

        if verbose:
            print('ROTATION INFO #'+str(i+1)+' =========================================================================')
            print('Origin:        [%+7.02f %+7.02f %+7.02f ]' % (o[0], o[1], o[2]))
            print()
            print('Pre-rotation ----------------------------')
            print('Point:         [%+7.02f %+7.02f %+7.02f ]' % (p[0], p[1], p[2]))
            print('Translation:   [%+7.02f %+7.02f %+7.02f ]' % (t[0], t[1], t[2]))
            print()
            print('Post-rotation ---------------------------')
            print('Point:         [%+7.02f %+7.02f %+7.02f ]' % (o[0]+th, o[1]+tp, o[2]+tb))
            print('Translation:   [%+7.02f %+7.02f %+7.02f ]' % (th, tp, tb))
            print()
            print('Rotation Matrix:')
            print('[ %+.02f %+.02f %+.02f\n  %+.02f %+.02f %+.02f\n  %+.02f %+.02f %+.02f ]' % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]))
            print()
            print('Heading -------------------| Pitch --------------------| Bank ---------------------|')
            print('a=%.6f rad (%.6f°), b=%.6f rad (%.6f°), c=%.6f rad (%.6f°)' % (a, a*180/pi, b, b*180/pi, c, c*180/pi))
            print('==========================================================================================')

    return rotated_points

def point_intersects_obb(point, obb_angle, obb_origin, obb_max, obb_min, verbose=False):
    if verbose:
        print('Transforming OBB => AABB for point intersection test.')
    point, aabb_max, aabb_min = apply_rotation_to_points([point, obb_max, obb_min], invert_angles(obb_angle), obb_origin)
    return point_intersects_aabb(point, aabb_max, aabb_min, verbose=verbose)

def point_intersects_aabb(point, aabb_max, aabb_min, verbose=False):
    intersection = (
        point[0] >= aabb_min[0] and
        point[0] <= aabb_max[0] and
        point[1] >= aabb_min[1] and
        point[1] <= aabb_max[1] and
        point[2] >= aabb_min[2] and
        point[2] <= aabb_max[2]
    )
    if verbose:
        print('INTERSECTION TEST:')
        print('box_max: %.02f %.02f %.02f' % (aabb_max[0], aabb_max[1], aabb_max[2]))
        print('box_min: %.02f %.02f %.02f' % (aabb_min[0], aabb_min[1], aabb_min[2]))
        print('point:   %.02f %.02f %.02f' % (point[0], point[1], point[2]))
        print(intersection)
    return intersection
