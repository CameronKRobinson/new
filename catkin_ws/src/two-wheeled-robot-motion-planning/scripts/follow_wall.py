#! /usr/bin/env python

# import ros stuff
import rospy
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from tf import transformations
from datetime import datetime

import random
import math
import time

hz = 20 #Cycle Frequency
loop_index = 0
loop_index_corner = 0
loop_index_v_angle = 0
inf = 5
wall_dist = 0.5    # Distance from the wall (0.13)
max_speed = 0.3
# Maximum speed of robot
p = 15    # Proportional constant for controller
d = 0  # Derivative constant for controller (d = 7)
angle = 1    # Proportional constant for angle controller (just simple P controller)
direction = -1    # 1 for wall on the left side of the robot (-1 for the right side)
e = 0
angle_min = 0    # Angle, at which was measured the shortest distance
dist_front = 0
diff_e = 0
dist_min = 0
last_corner_detection_time = time.time()
last_change_direction_time = time.time()
last_v_angle_detection_time = time.time()
rotating = 0
pub_ = None
regions_ = {
        'bright': 0,
        'right': 0,
        'fright': 0,
        'front': 0,
        'left': 0,
}
state_ = 0
inner = 0 # TODO: Mudar para 0
list_state=[0, 0, 0, 0, 0]
list_state_length = 5
index = 0

state_corner_inner=[0, 0, 0]
state_corner_inner_length = 3
index_state_corner_inner = 0

bool_corner = 0
bool_v_angle =0
line = 0
last_vel = [random.uniform(-0,0.3),  random.uniform(-0.3,0.3)]
x = 0
wall_found =0
state_dict_ = {
    0: 'find the wall',
    1: 'follow the wall',
    3: 'go back'
}

def clbk_laser(msg):
    global regions_, e, angle_min, dist_front, diff_e, direction, bool_corner, bool_v_angle, index, list_state, list_state_length
    size = len(msg.ranges)
    min_index = size*(direction+1)/4
    max_index = size*(direction+3)/4

    for i in range(min_index, max_index):
        if msg.ranges[i] < msg.ranges[min_index] and msg.ranges[i] > 0.01:
            min_index = i
    angle_min = (min_index-size/2)*msg.angle_increment
    dist_min = msg.ranges[min_index]
    dist_front = msg.ranges[size/2]
    diff_e = min((dist_min - wall_dist) - e, 100)
    e = min(dist_min - wall_dist, 100)

    regions_ = {
        'bright':  min(min(msg.ranges[0:143]), inf),
        'right': min(min(msg.ranges[144:287]), inf),
        'fright':  min(min(msg.ranges[288:431]), inf),
        'front':  min(min(msg.ranges[432:575]), inf),
        'fleft':   min(min(msg.ranges[576:719]), inf),
        'left':   min(min(msg.ranges[720:863]), inf),
        'bleft':   min(min(msg.ranges[864:1007]), inf),
    }
    bool_corner = is_corner()
    bool_v_angle = is_v_angle()
    if bool_corner == 0 and bool_v_angle == 0:
        list_state[index]=0

    index = index + 1 #5 samples recorded to asses if we are at the corner or not
    if index == list_state_length:
        index = 0

    take_action()

def change_state(state):
    global state_, state_dict_
    if state is not state_:
        #print 'Wall follower - [%s] - %s' % (state, state_dict_[state])
        state_ = state

def take_action():
    global regions_, inner, index, list_state, index_state_corner_inner, state_corner_inner_length, state_corner_inner, loop_index, loop_index_corner, loop_index_v_angle
    global wall_dist, max_speed, direction, p, d, angle, dist_min, line, inner, wall_found, rotating, bool_corner, bool_v_angle

    regions = regions_
    msg = Twist()
    linear_x = 0
    angular_z = 0
    
    #print direction
    state_description = ''

    rotate_sequence = ['C', 'C', 'C']
    if rotating == 1:
        #print 'Keep rotating'
        state_description = 'case 2 - keep rotationg'
        change_state(3)
        if(regions['left'] < wall_dist or regions['right'] < wall_dist):
            rotating = 0
    elif regions['fright'] == inf and regions['front'] == inf and regions['right'] == inf and regions['bright'] == inf and regions['fleft'] == inf and regions['left'] == inf and regions['bleft'] == inf and wall_found == 0:
        state_description = 'case 1 - nothing'
        change_state(0)
    elif (loop_index == loop_index_corner) and (rotate_sequence == state_corner_inner):
        #print 'Start rotating'
        change_direction()
        state_corner_inner = [ 0, 0, 'C']
        change_state(3)
    else:
        state_description = 'There is a Wall'
        change_state(1)
        wall_found = 1
    #print state_description

    #rospy.loginfo(regions)
    regionsAux = regions_
    for key in regions:
       if regions[key] ==inf:
           regionsAux[key]='inf'
       elif regions[key] >= wall_dist:
           regionsAux[key]= 'longe'
       else:
           regionsAux[key] = 'perto'
    for x in regionsAux:
        print x + ': ' + regionsAux[x] + '; ',
    print '\n'
    lenAux = len(state_corner_inner)
    print lenAux
    for key_state in range(0, state_corner_inner_length):
        print state_corner_inner[key_state],
    print '\n'

def find_wall():
    global direction, last_vel, x
    x = x + 1
    msg = Twist()
    #msg.linear.x = last_vel[0] +0.0003
    #msg.angular.z= -0.3
    msg.linear.x = max(min( last_vel[0] + random.uniform(-0.01,0.01),0.3),0)
    msg.angular.z= max(min( last_vel[1] + random.uniform(-0.1,0.1),0.3),-0.3)
    last_vel[0] = msg.linear.x
    last_vel[1] = msg.angular.z
    #print 'Find Wall - linear, angular %f - %f' %(msg.linear.x, msg.angular.z)
    return msg

def PD_wallFollowing():
    global wall_dist, max_speed, direction, p, d, angle, dist_min, dist_front, e, diff_e, angle_min
    msg = Twist()
    #print '%f %f'%(e, diff_e)

    if dist_front < wall_dist:
        msg.linear.x = 0
    elif dist_front < wall_dist*2:
        msg.linear.x = 0.5*max_speed
    elif abs(angle_min) > 1.75:
        msg.linear.x = 0.4*max_speed
    else:
        msg.linear.x = max_speed
    #print 'e, diff_e, angle, angle_min %s  - %s - %s - %s ' % ( e, diff_e, angle, angle_min)
    #msg.angular.z = 0.3
    msg.angular.z = max(min(direction*(p*e+d*diff_e) + angle*(angle_min-((math.pi)/2)*direction), 2.5), -2.5)
    #print 'Turn Left angular z, linear x %f - %f' % (msg.angular.z, msg.linear.x)
    return msg


def change_direction():
    global direction, last_change_direction, rotating
    print 'Change direction!'
    elapsed_time = time.time() - last_change_direction_time #Elapsed time since last change direction
    if elapsed_time >= 20:
        last_change_direction = time.time()
        direction = -direction #Wall in the other side now
        rotating = 1

def go_back():
    global direction
    msg = Twist()
    msg.linear.x = 0
    msg.angular.z = direction*2
    return msg


def is_corner():
    global regions_, list_state, list_state_length, last_corner_detection_time, index, state_corner_inner, index_state_corner_inner, loop_index, loop_index_corner
    regions = regions_
    bool_corner = 0
    if (regions['fright'] == inf and regions['front'] == inf and regions['right'] == inf and regions['bright'] < inf  and regions['left'] == inf and regions['bleft'] == inf and regions['fleft'] == inf) or (regions['bleft'] < inf and regions['fleft'] == inf and regions['front'] == inf and regions['left'] == inf and regions['right'] == inf and regions['bright'] == inf and regions['fright'] == inf):
        bool_corner = 1 #bool is corner
        state_description = 'corner of V'
        list_state[index]='C' # it is true that we are at the V
        elapsed_time = time.time() - last_corner_detection_time #Elapsed time since last corner detection
        #print 'index ... corner count %f   %s' %(index, list_state.count('C'))
        if list_state.count('C')== list_state_length and elapsed_time >= 30:
            last_corner_detection_time = time.time()
            loop_index_corner = loop_index
            state_corner_inner = state_corner_inner[1:]
            state_corner_inner.append('C')
            #index_state_corner_inner = index_state_corner_inner+1
            #if index_state_corner_inner == state_corner_inner_length:
            #    index_state_corner_inner = 0
            print 'CORNER'
    return bool_corner # bool is not corner

def is_v_angle():
    global regions_, wall_dist, list_state, list_state_length, last_v_angle_detection_time, index, state_corner_inner, index_state_corner_inner, loop_index_v_angle, loop_index
    regions = regions_
    bool_v_angle = 0
    if regions['fright'] < wall_dist and regions['front'] < wall_dist and regions['fleft'] < wall_dist:
        bool_v_angle = 1
        state_description = 'inner v angle'
        #print state_description
        list_state[index]='I'
        elapsed_time = time.time() - last_v_angle_detection_time #Elapsed time since last corner detection
        if list_state.count('I')==list_state_length and elapsed_time >= 20:
            last_v_angle_detection_time = time.time()
            loop_index_v_angle = loop_index
            state_corner_inner = state_corner_inner[1:]
            state_corner_inner.append('I')
            #state_corner_inner [index_state_corner_inner] = 'I'
            #index_state_corner_inner = index_state_corner_inner+1
            #if index_state_corner_inner == state_corner_inner_length:
            #    index_state_corner_inner = 0
            print 'V_angle'
    return bool_v_angle #bool is not v_angle

def main():
    global pub_, active_, hz, loop_index
    
    rospy.init_node('reading_laser')
    
    pub_ = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
    
    sub = rospy.Subscriber('/m2wr/laser/scan', LaserScan, clbk_laser)
    
    print 'Code is running'
    rate = rospy.Rate(hz)
    while not rospy.is_shutdown():
        loop_index = loop_index + 1
        msg = Twist()
        if state_ == 0:
            msg = find_wall()
        elif state_ == 1:
            msg = PD_wallFollowing()
        elif state_ == 3:
            msg = go_back()
        else:
            rospy.logerr('Unknown state!')
        
        pub_.publish(msg)
        
        rate.sleep()

if __name__ == '__main__':
    main()