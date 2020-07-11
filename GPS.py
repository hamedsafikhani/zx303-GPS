#!/bin/python

from dotenv import load_dotenv
from socket import AF_INET, socket, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from threading import Thread
from datetime import datetime
from dateutil import tz
import googlemaps
import math
import os
import requests
import json
import psycopg2

#TODO
def logdb(imei, protocol_name, terminal_server, server_terminal, ip):
    connection = psycopg2.connect(user=,
                                  password=,
                                  host=,
                                  port=,
                                  database=)
    cursor = connection.cursor()
    cursor.execute(f"""INSERT INTO public.log(
	    imei, protocol_name, terminal_server, server_terminal, time_st, ip)
	    VALUES ('{imei}', '{protocol_name}', '{terminal_server}', '{server_terminal}','{str(datetime.now())}', '{ip}');""")
    connection.commit()
    connection.close()
    
def accept_incoming_connections():
    """
    Accepts any incoming client connexion 
    and starts a dedicated thread for each client.
    """
    
    while True:
        client, client_address = SERVER.accept()
        print('%s:%s has connected.' % client_address)
        
        # Initialize the dictionaries
        addresses[client] = {}
        status[client] = {}
        positions[client] = {}
        
        # Add current client address into adresses
        addresses[client]['address'] = client_address
        logdb('null', 'null', 'null', 'null', addresses[client]['address'][0])
        
        Thread(target=handle_client, args=(client,)).start()

def LOGGER(event, filename, ip, client, type, data):
    """
    A logging function to store all input packets, 
    as well as output ones when they are generated.

    There are two types of logs implemented: 
        - a general (info) logger that will keep track of all 
            incoming and outgoing packets,
        - a position (location) logger that will write to a 
            file contianing only results og GPS or LBS data.
    """
    
    with open(os.path.join('./logs/', filename), 'a+') as log:
        if (event == 'info'):
            # TSV format of: Timestamp, Client IP, IN/OUT, Packet
            logMessage = datetime.now().strftime('%Y/%m/%d %H:%M:%S') + '\t' + ip + '\t' + client + '\t' + type + '\t' + data + '\n'
        elif (event == 'location'):
            # TSV format of: Timestamp, Client IP, Location DateTime, GPS/LBS, Validity, Nb Sat, Latitude, Longitude, Accuracy, Speed, Heading
            logMessage = datetime.now().strftime('%Y/%m/%d %H:%M:%S') + '\t' + ip + '\t' + client + '\t' + '\t'.join(list(str(x) for x in data.values())) + '\n'
        log.write(logMessage)


def handle_client(client):
    """
    Takes client socket as argument. 
    Handles a single client connection, by listening indefinitely for packets.
    """

    # Initialize dictionaries for that client
    positions[client]['wifi'] = []
    positions[client]['gsm-cells'] = []
    positions[client]['gsm-carrier'] = {}
    positions[client]['gps'] = {}

    # Keep receiving and analyzing packets until end of time
    # or until device sends disconnection signal
    keepAlive = True
    while (True):

        # Handle socket errors with a try/except approach
        try:
            packet = client.recv(BUFSIZ)
            print("pkpkpk :::::::::",packet)
            # Only process non-empty packets
            if (len(packet) > 0):
                print('[', addresses[client]['address'][0], ']', 'IN Hex :', packet.hex(), '(length in bytes =', len(packet), ')')
                keepAlive = read_incoming_packet(client, packet)
                LOGGER('info', 'server_log.txt', addresses[client]['address'][0], addresses[client]['imei'], 'IN', packet.hex())
                logdb(addresses[client]['imei'], 'null', packet.hex(), 'null',addresses[client]['address'][0])
                # Disconnect if client sent disconnect signal
                #if (keepAlive is False):
                #    print('[', addresses[client]['address'][0], ']', 'DISCONNECTED: socket was closed by client.')
                #    client.close()
                #    break

            # Close socket if recv() returns 0 bytes, i.e. connection has been closed
            else:

                logdb(addresses[client]['imei'], 'null', 'DISCONNECTED', 'DISCONNECTED',addresses[client]['address'][0])
                print('[', addresses[client]['address'][0], ']', 'DISCONNECTED: socket was closed for an unknown reason.')
                client.close()
                break                

        # Something went sideways... close the socket so that it does not hang
        except Exception as e:
            logdb(addresses[client]['imei'], 'null', 'DISCONNECTED', 'DISCONNECTED',addresses[client]['address'][0])
            print('[', addresses[client]['address'][0], ']', 'ERROR: socket was closed due to the following exception:')
            print(e)
            client.close()
            break
    print("This thread is now closed.")


def read_incoming_packet(client, packet):
    """
    Handle incoming packets to identify the protocol they are related to,
    and then redirects to response functions that will generate the apropriate 
    packet that should be sent back.
    Actual sending of the response packet will be done by an external function.
    """
    
    print("packet :::::::::::::: > ",packet )
    try:
        connection = psycopg2.connect(user=,
                                      password=,
                                      host=,
                                      port=,
                                      database=)
        cursor = connection.cursor()
        cursor.execute(f"""
        select message from sendmsg where done = False and imei = '{addresses[client]['imei']}'
        """)

        a = cursor.fetchall()
        for i in a:
            print(i[0])
            #send i[0]
            client.send(bytes.fromhex(i[0]))
            cursor.execute(f"""
            update sendmsg set done = True where message = '{i[0]}' and imei = '{addresses[client]['imei']}'
            """)
            print("SEND : ",i[0])
        connection.commit()
        connection.close()
    except Exception as e:
        print("IN SEND DATA : ",e)
        pass


   
  
    packet_list = [packet.hex()[i:i+2] for i in range(4, len(packet.hex())-4, 2)]

    pklist = ', '
    pklist.join(packet_list)

        
    protocol_name = protocol_dict['protocol'][packet_list[1]]
    protocol = protocol_name
    protocol_method = protocol_dict['response_method'][protocol_name]
    print('The current packet is for protocol:', protocol_name, 'which has method:', protocol_method)
    # Get the protocol name and react accordingly
    if (protocol_name == 'login'):
        r = answer_login(client, packet_list)
        logdb(addresses[client]['imei'], protocol_name, pklist, str(r), addresses[client]['address'][0])
    
    elif (protocol_name == 'gps_positioning' or protocol_name == 'gps_offline_positioning'):
        r = answer_gps(client, packet_list)
        logdb(addresses[client]['imei'], protocol_name, pklist, str(r), addresses[client]['address'][0])

    elif (protocol_name == 'status'):
        # Status can sometimes carry signal strength and sometimes not
        if (packet_list[0] == '06'): 
            print('[', addresses[client]['address'][0], ']', 'STATUS : Battery =', int(packet_list[2], base=16), '; Sw v. =', int(packet_list[3], base=16), '; Status upload interval =', int(packet_list[4], base=16))
        elif (packet_list[0] == '07'): 
            print('[', addresses[client]['address'][0], ']', 'STATUS : Battery =', int(packet_list[2], base=16), '; Sw v. =', int(packet_list[3], base=16), '; Status upload interval =', int(packet_list[4], base=16), '; Signal strength =', int(packet_list[5], base=16))
        # Exit function without altering anything
        status[client]['status'] ='Battery =:' + str(int(packet_list[2], base=16)) + ': Sw v. =:' + str(int(packet_list[3], base=16)) + ': Status upload interval =:' + str(int(packet_list[4], base=16) )+ ': Signal strength =:'+ str(int(packet_list[5], base=16))
        logdb(addresses[client]['imei'], protocol_name, pklist, '', addresses[client]['address'][0])
        return(True)
    
    elif (protocol_name == 'hibernation'):
        # Exit function returning False to break main while loop in handle_client()
        print('[', addresses[client]['address'][0], ']', 'STATUS : Sent hibernation packet. Disconnecting now.')
        logdb(addresses[client]['imei'], protocol_name, pklist, 'Sent hibernation packet. Disconnecting now.', addresses[client]['address'][0])
        return(False)

    elif (protocol_name == 'setup'):
        # TODO: HANDLE NON-DEFAULT VALUES
        r = answer_setup(packet_list, '0300', '00110001', '000000', '000000', '000000', '00', '000000', '000000',
                         '000000', '00', '0000', '0000', ['', '', ''])        
        logdb(addresses[client]['imei'], protocol_name, pklist, str(r), addresses[client]['address'][0])
        #r = answer_setup(packet_list, '0010', '00110001', '000000', '000000', '000000', '00', '000000', '000000', '000000', '00', '0000', '0000', ['', '', ''])
#7878 1E 57 0006 31 000000 000000 000000 00 000000000000000000 00 00000000 3B3B 0D0A
#7878 1E 57 0300 31 000000 000000 000000 00 000000000000000000 00 00000000 3B3B 0D0A
#7878 1E 57 0006 31 000000 000000 000000 00 000000000000000000 00 00000000 3B3B 0D0A
    elif (protocol_name == 'time'):
        r = answer_time(packet_list)
        logdb(addresses[client]['imei'], protocol_name, pklist, str(r), addresses[client]['address'][0])

    elif (protocol_name == 'wifi_positioning' or protocol_name == 'wifi_offline_positioning'):
        r = answer_wifi_lbs(client, packet_list)
        logdb(addresses[client]['imei'], protocol_name, pklist, str(r), addresses[client]['address'][0])

    elif (protocol_name == 'position_upload_interval'):
        r = answer_upload_interval(client, packet_list)
        logdb(addresses[client]['imei'], protocol_name, pklist, str(r), addresses[client]['address'][0])

    else:
        r = generic_response(packet_list[1])
        logdb(addresses[client]['imei'], '?', pklist, str(r), addresses[client]['address'][0])
    
    # Send response to client
    print('------->[', addresses[client]['address'][0], ']', 'OUT Hex :', r, '(length in bytes =', len(bytes.fromhex(r)), ')')
    if r[6:8] != '80':
        send_response(client, r)
        logdb(addresses[client]['imei'], '?', 'NULL', str(r), addresses[client]['address'][0])
    else:
        pass
    # Return True to avoid failing in main while loop in handle_client()
    return(True)


def answer_login(client, query):
    protocol = query[1]
    addresses[client]['imei'] = ''.join(query[2:10])[1:]
    addresses[client]['software_version'] = int(query[10], base=16)

    # DEBUG: Print IMEI and software version
    print("Detected IMEI :", addresses[client]['imei'], "and Sw v. :", addresses[client]['software_version'])

    # Prepare response: in absence of control values, 
    # always accept the client
    response = '01'
    # response = '44'
    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r)

def answer_setup(query, uploadIntervalSeconds, binarySwitch, alarm1, alarm2, alarm3, dndTimeSwitch, dndTime1, dndTime2, dndTime3, gpsTimeSwitch, gpsTimeStart, gpsTimeStop, phoneNumbers):
    
    protocol = query[1]
    binarySwitch = format(int(binarySwitch, base=2), '02X')

    # Convert phone numbers to 'ASCII' (?) by padding each digit with 3's and concatenate
    for n in range(len(phoneNumbers)):
        phoneNumbers[n] = bytes(phoneNumbers[n], 'UTF-8').hex()
    phoneNumbers = '3B'.join(phoneNumbers)

    # Build response
    response = uploadIntervalSeconds + binarySwitch + alarm1 + alarm2 + alarm3 + dndTimeSwitch + dndTime1 + dndTime2 + dndTime3 + gpsTimeSwitch + gpsTimeStart + gpsTimeStop + phoneNumbers
    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r)


def answer_time(query):
    """
    Time synchronization is initiated by the device, which expects a response
    contianing current datetime over 7 bytes: YY YY MM DD HH MM SS.
    This function is a wrapper to generate the proper response
    """
    
    # Read protocol
    protocol = query[1]

    # Get current date and time into the pretty-fied hex format
    response = get_hexified_datetime(truncatedYear=False)

    # Build response
    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r)


def answer_gps(client, query):
    positions[client]['gps'] = {}

    # Read protocol
    protocol = query[1]

    # Extract datetime from incoming query to put into the response
    # Datetime is in HEX format here, contrary to LBS packets...
    # That means it's read as HEX(YY) HEX(MM) HEX(DD) HEX(HH) HEX(MM) HEX(SS)...
    dt = ''.join([ format(int(x, base = 16), '02d') for x in query[2:8] ])
    # GPS DateTime is at UTC timezone: we need to convert it to local, while keeping the same format as a string
    if (dt != '000000000000'): 
        dt = datetime.strftime(datetime.strptime(dt, '%y%m%d%H%M%S').replace(tzinfo=tz.tzutc()).astimezone(tz.tzlocal()), '%y%m%d%H%M%S')
    # Read in the incoming GPS positioning
    # Byte 8 contains length of packet on 1st char and number of satellites on 2nd char
    gps_data_length = int(query[8][0], base=16)
    gps_nb_sat = int(query[8][1], base=16)
    # Latitude and longitude are both on 4 bytes, and were multiplied by 30000
    # after being converted to seconds-of-angle. Let's convert them back to degree
    gps_latitude = int(''.join(query[9:13]), base=16) / (30000 * 60)
    gps_longitude = int(''.join(query[13:17]), base=16) / (30000 * 60)
    # Speed is on the next byte
    gps_speed = int(query[17], base=16)
    # Last two bytes contain flags in binary that will be interpreted
    gps_flags = format(int(''.join(query[18:20]), base=16), '0>16b')
    position_is_valid = gps_flags[3]
    # Flip sign of GPS latitude if South, longitude if West
    if (gps_flags[4] == '1'):
        gps_latitude = -gps_latitude
    if (gps_flags[5] == '0'):
        gps_longitude = -gps_longitude
    gps_heading = int(''.join(gps_flags[6:]), base = 2)

    # Store GPS information into the position dictionary and print them
    positions[client]['gps']['method'] = 'GPS'
    # In some cases dt is empty with value '000000000000': let's avoid that because it'll crash strptime
    positions[client]['gps']['datetime'] = datetime.strptime(datetime.now().strftime('%y%m%d%H%M%S') if dt == '000000000000' else dt, '%y%m%d%H%M%S').strftime('%Y/%m/%d %H:%M:%S')
    positions[client]['gps']['valid'] = position_is_valid
    positions[client]['gps']['nb_sat'] = gps_nb_sat
    positions[client]['gps']['latitude'] = gps_latitude
    positions[client]['gps']['longitude'] = gps_longitude
    positions[client]['gps']['accuracy'] = 0.0
    positions[client]['gps']['speed'] = gps_speed
    positions[client]['gps']['heading'] = gps_heading
    a = open('./gpsdataGPS','w')
    a.write("GPSlat:{}:GPSlon:{}".format(gps_latitude,gps_longitude))
    print('***************************[', addresses[client]['address'][0], ']', "POSITION/GPS : Valid =", position_is_valid, "; Nb Sat =", gps_nb_sat, "; Lat =", gps_latitude, "; Long =", gps_longitude, "; Speed =", gps_speed, "; Heading =", gps_heading,'***********')
    LOGGER('location', 'location_log.txt', addresses[client]['address'][0], addresses[client]['imei'], '', positions[client]['gps'])
    connection = psycopg2.connect(user=,
                              password=,
                              host=,
                              port=,
                              database=)
    cursor = connection.cursor()
    try:
        cursor.execute(f"""insert into public.gpsdata(address,imei, lat_long, time_st, lbs,status,protocol) 
                    VALUES ('{addresses[client]['address'][0]}','{addresses[client]['imei']}', '{str(gps_latitude)+":"+str(gps_longitude)}','{str(datetime.now())}', False,'{"Speed: "+{str(gps_speed)}+status[client]['status']}','{protocol}');""")
    except:
        cursor.execute(f"""insert into public.gpsdata(address,imei, lat_long, time_st, lbs,status,protocol) 
                    VALUES ('{addresses[client]['address'][0]}','{addresses[client]['imei']}', '{str(gps_latitude)+":"+str(gps_longitude)}','{str(datetime.now())}', False,'NOT RECIEVED','{protocol}');""")

    #             print("PUBLISH TO from DEV")
    connection.commit()
    connection.close()





    # Get current datetime for answering
    response = get_hexified_datetime(truncatedYear=True)
    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])

    #send_response(client, '787801800D0A' )
    return(r)


def answer_wifi_lbs(client, query):

    positions[client]['wifi'] = []
    positions[client]['gsm-cells'] = []
    positions[client]['gsm-carrier'] = {}
    positions[client]['gps'] = {}

    # Read protocol
    protocol = query[1]

    # Datetime is BCD-encoded in bytes 2:7, meaning it's read *directly* as YY MM DD HH MM SS
    # and does not need to be decoded from hex. YY value above 2000.
    dt = ''.join(query[2:8])
    # WiFi DateTime seems to be UTC timezone: convert it to local, while keeping the same format as a string
    if (dt != '000000000000'): 
        dt = datetime.strftime(datetime.strptime(dt, '%y%m%d%H%M%S').replace(tzinfo=tz.tzutc()).astimezone(tz.tzlocal()), '%y%m%d%H%M%S')

    # WIFI
    n_wifi = int(query[0])
    if (n_wifi > 0):
        for i in range(n_wifi):
            current_wifi = {'macAddress': ':'.join(query[(8 + (7 * i)):(8 + (7 * (i + 1)) - 2 + 1)]), # That +1 is because l[start:stop] returnes elements from start to stop-1...
                            'signalStrength': -int(query[(8 + (7 * (i + 1)) - 1)], base = 16)}
            positions[client]['wifi'].append(current_wifi)
            
            # Print Wi-Fi hotspots into the logs
            print('[', addresses[client]['address'][0], ']', "POSITION/WIFI : BSSID =", current_wifi['macAddress'], "; RSSI =", current_wifi['signalStrength'])

    # GSM Cell towers
    n_gsm_cells = int(query[(8 + (7 * n_wifi))])
    # The first three bytes after n_lbs are MCC(2 bytes)+MNC(1 byte)
    gsm_mcc = int(''.join(query[((8 + (7 * n_wifi)) + 1):((8 + (7 * n_wifi)) + 2 + 1)]), base=16)
    gsm_mnc = int(query[((8 + (7 * n_wifi)) + 3)], base=16)
    positions[client]['gsm-carrier']['n_gsm_cells'] = n_gsm_cells
    positions[client]['gsm-carrier']['MCC'] = gsm_mcc
    positions[client]['gsm-carrier']['MNC'] = gsm_mnc
    print("--------------------------------WIFI: ", positions[client]['wifi'])

    if (n_gsm_cells > 0):
        for i in range(n_gsm_cells):
            current_gsm_cell = {'locationAreaCode': int(''.join(query[(((8 + (7 * n_wifi)) + 4) + (5 * i)):(((8 + (7 * n_wifi)) + 4) + (5 * i) + 1 + 1)]), base=16),
                                'cellId': int(''.join(query[(((8 + (7 * n_wifi)) + 4) + (5 * i) + 1 + 1):(((8 + (7 * n_wifi)) + 4) + (5 * i) + 2 + 1 + 1)]), base=16),
                                'signalStrength': -int(query[(((8 + (7 * n_wifi)) + 4) + (5 * i) + 2 + 1 + 1)], base=16)}
            positions[client]['gsm-cells'].append(current_gsm_cell)
            
            # Print LBS data into logs as well
            print('[', addresses[client]['address'][0], ']', "POSITION/LBS : LAC =", current_gsm_cell['locationAreaCode'], "; CellID =", current_gsm_cell['cellId'], "; MCISS =", current_gsm_cell['signalStrength'])
    
    r_1 = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, dt, hex_dict['stop_1'] + hex_dict['stop_2'])
    print('[', addresses[client]['address'][0], ']', 'OUT Hex :', r_1, '(length in bytes =', len(bytes.fromhex(r_1)), ')')
    send_response(client, r_1)
    print("*/*/*/*/*/*/*/*/*/ " , positions[client]['gsm-cells'])
    #response = '2C'.join(
       # [ bytes(positions[client]['gps']['latitude'][0] + str(round(float(positions[client]['gps']['latitude'][1:]), 6)), 'UTF-8').hex(), 
       # bytes(positions[client]['gps']['longitude'][0] + str(round(float(positions[client]['gps']['longitude'][1:]), 6)), 'UTF-8').hex() ])
        #TODO
        #TODO
        #TODO
    mmc  = gsm_mcc
    mnc  = gsm_mnc
    print ("<<MMC and MNC>> : ",mmc,mnc)  
    url = "https://us1.unwiredlabs.com/v2/process.php"
   
    cc = str(positions[client]['wifi'])
    lbs = str(positions[client]['gsm-cells'])
    payload = "{\"token\": \"09ce33ba16479e\",\"radio\": \"gsm\",\"mcc\": %s,\"mnc\": %s,"%(mmc,mnc) + "\"cells\": " +         lbs.replace("locationAreaCode","lac").replace("cellId","cid").replace("signalStrength","signal")+ ", \"wifi\": "+cc.replace("macAddress","bssid").replace("signalStrength","signal") + "}"
    print(payload.replace("\'","\""))
    payload = payload.replace("\'","\"")
    #payload = ("{\"token\": \"09ce33ba16479e\",\"radio\": \"gsm\",\"mcc\": %s,\"mnc\": %s,\"cells\":"%(mmc,mnc) ) + format_gps_data + ",\"address\": 1}"
    #payload = str(payload).replace("'","\"")
    response = requests.request("POST", url, data=payload)
    print(response.text)

    aa = response.text
    lat = aa.split("\"lat\":")[1].split("\"lon\":")[0].split(",")[0]
    lon = aa.split("\"lat\":")[1].split("\"lon\":")[1].split(",")[0]
    print(lat)
    print(lon)
    response = '2C'.join(
        [ bytes(lat + str(round(float(lat[1:]), 6)), 'UTF-8').hex(),
        bytes(lon + str(round(float(lon[1:]), 6)), 'UTF-8').hex() ])
    # r_2 = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])
    print(response)
    f = open('./dataLBS','w')
    f.write('LBSLAT:{}:LBSlon:{}'.format(lat,lon))

    connection = psycopg2.connect(user=,
                              password=,
                              host=,
                              port=,
                              database=)
    cursor = connection.cursor()
    try:
        cursor.execute(f"""insert into public.gpsdata(address,imei, lat_long, time_st, lbs,status,protocol) 
                        VALUES ('{addresses[client]['address'][0]}','{addresses[client]['imei']}', '{str(lat)+":"+str(lon)}','{str(datetime.now())}', True,'{status[client]['status']}','{protocol}');""")
    except:
        try:
            cursor.execute(f"""insert into public.gpsdata(address,imei, lat_long, time_st, lbs,status,protocol) 
                        VALUES ('{addresses[client]['address'][0]}','{addresses[client]['imei']}', '{str(lat)+":"+str(lon)}','{str(datetime.now())}', True,'NOT RECIEVED','{protocol}');""")
        except Exception as e :
            pass

    connection.commit()
    connection.close()



    r_2 = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r_2)


def answer_upload_interval(client, query):
    """
    Whenever the device received an SMS that changes the value of an upload interval,
    it sends this information to the server.
    The server should answer with the exact same content to acknowledge the packet.
    """

    # Read protocol
    protocol = query[1]

    # Response is new upload interval reported by device (HEX formatted, no need to alter it)
    response = ''.join(query[2:4])

    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r)


def generic_response(protocol):
    """
    Many queries made by the device do not expect a complex
    response: most of the times, the device expects the exact same packet.
    Here, we will answer with the same value of protocol that the device sent, 
    not using any content.
    """
    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, None, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r)


def make_content_response(start, protocol, content, stop):
    """
    This is just a wrapper to generate the complete response
    to a query, goven its content.
    It will apply to all packets where response is of the format:
    start-start-length-protocol-content-stop_1-stop_2.
    Other specific packets where length is replaced by counters
    will be treated separately.
    """
    return(start + format((len(bytes.fromhex(content)) if content else 0)+1, '02X') + protocol + (content if content else '') + stop)


def send_response(client, response):
    """
    Function to send a response packet to the client.
    """
    LOGGER('info', 'server_log.txt', addresses[client]['address'][0], addresses[client]['imei'], 'OUT', response)
    client.send(bytes.fromhex(response))


def get_hexified_datetime(truncatedYear):
    """
    Make a fancy function that will return current GMT datetime as hex
    concatenated data, using 2 bytes for year and 1 for the rest.
    The returned string is YY YY MM DD HH MM SS if truncatedYear is False,
    or just YY MM DD HH MM SS if truncatedYear is True.
    """

    # Get current GMT time into a list
    if (truncatedYear):
        dt = datetime.utcnow().strftime('%y-%m-%d-%H-%M-%S').split("-")
    else:
        dt = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S').split("-")
    print("DTTTTTTTTT in func :",dt)
    # Then convert to hex with 2 bytes for year and 1 for the rest
    dt = [ format(int(x), '0'+str(len(x))+'X') for x in dt ]
    return(''.join(dt))


def GoogleMaps_geolocation_service(gmapsClient, positionDict):
    """
    This wrapper function will query the Google Maps API with the list
    of cell towers identifiers and WiFi SSIDs that the device detected.
    It requires a Google Maps API key.
    
    For now, the radio_type argument is forced to 'gsm' because there are 
    no CDMA cells in France (at least that's what I believe), and since the
    GPS device only handles 2G, it's the only option available.
    The carrier is forced to 'Free' since that's the one for the SIM card
    I'm using, but again this would need to be tweaked (also it probbaly
    doesn't make much of a difference to feed it to the function or not!)
    
    These would need to be tweaked depending on where you live.

    A nice source for such data is available at https://opencellid.org/
    """
    print('Google Maps Geolocation API queried with:', positionDict)
    geoloc = gmapsClient.geolocate(home_mobile_country_code=positionDict['gsm-carrier']['MCC'], 
        home_mobile_network_code=positionDict['gsm-carrier']['MCC'], 
        radio_type='gsm', 
        carrier='Free', 
        consider_ip='true', 
        cell_towers=positionDict['gsm-cells'], 
        wifi_access_points=positionDict['wifi'])

    print('Google Maps Geolocation API returned:', geoloc)
    return(geoloc)

"""
This is a debug block to test the GeoLocation API

gmaps.geolocate(home_mobile_country_code='208', home_mobile_network_code='01', radio_type=None, carrier=None, consider_ip=False, cell_towers=cell_towers, wifi_access_points=None)

## DEBUG: USE DATA FROM ONE PACKET
# Using RSSI
cell_towers = [
    {
        'locationAreaCode': 832,
        'cellId': 51917,
        'signalStrength': -90  
    },
    {
        'locationAreaCode': 768,
        'cellId': 64667,
        'signalStrength': -100
    },
    {
        'locationAreaCode': 1024,
        'cellId': 24713,
        'signalStrength': -100
    },
    {
        'locationAreaCode': 768,
        'cellId': 53851,
        'signalStrength': -100
    },
    {
        'locationAreaCode': 1024,
        'cellId': 8021,
        'signalStrength': -100
    },
    {
        'locationAreaCode': 1024,
        'cellId': 62216,
        'signalStrength': -100
    }
]

# Using dummy values in dBm
cell_towers = [
    {
        'locationAreaCode': 832,
        'cellId': 51917,
        'signalStrength': -50  
    },
    {
        'locationAreaCode': 768,
        'cellId': 64667,
        'signalStrength': -30
    },
    {
        'locationAreaCode': 1024,
        'cellId': 24713,
        'signalStrength': -30
    },
    {
        'locationAreaCode': 768,
        'cellId': 53851,
        'signalStrength': -30
    },
    {
        'locationAreaCode': 1024,
        'cellId': 8021,
        'signalStrength': -30
    },
    {
        'locationAreaCode': 1024,
        'cellId': 62216,
        'signalStrength': -30
    }
]
"""

# Declare common Hex codes for packets
hex_dict = {
    'start': '78', 
    'stop_1': '0D', 
    'stop_2': '0A'
}

protocol_dict = {
    'protocol': {
        '01': 'login',
        '05': 'supervision',
        '08': 'heartbeat', 
        '10': 'gps_positioning', 
        '11': 'gps_offline_positioning', 
        '13': 'status', 
        '14': 'hibernation', 
        '15': 'reset', 
        '16': 'whitelist_total', 
        '17': 'wifi_offline_positioning', 
        '30': 'time', 
        '43': 'mom_phone_WTFISDIS?', 
        '56': 'stop_alarm', 
        '57': 'setup', 
        '58': 'synchronous_whitelist', 
        '67': 'restore_password', 
        '69': 'wifi_positioning', 
        '80': 'manual_positioning', 
        '81': 'battery_charge', 
        '82': 'charger_connected', 
        '83': 'charger_disconnected', 
        '94': 'vibration_received', 
        '98': 'position_upload_interval',
        'b3': 'B3',
        '99': '99',
        '92': '92',
        '49': '49',
        '64': 'recording_request'
    }, 
    'response_method': {
        'login': 'login',
        'logout': 'logout', 
        'supervision': '',
        'heartbeat': '', 
        'gps_positioning': 'datetime_response', 
        'gps_offline_positioning': 'datetime_response', 
        'status': '', 
        'hibernation': '', 
        'reset': '', 
        'whitelist_total': '', 
        'wifi_offline_positioning': 'datetime_position_response', 
        'time': 'time_response', 
        'stop_alarm': '', 
        'setup': 'setup', 
        'synchronous_whitelist': '', 
        'restore_password': '', 
        'wifi_positioning': 'datetime_position_response', 
        'manual_positioning': '', 
        'battery_charge': '', 
        'charger_connected': '', 
        'charger_disconnected': '', 
        'vibration_received': '', 
        'position_upload_interval': 'upload_interval_response',
        'B3': '',
        '99': '',
        '92': '',
        '49' : '',
        'recording_request':''
    }
}


# Import dotenv with API keys and initialize API connections

# Details about host server
HOST = 
PORT = 
BUFSIZ = 10240 #4096
ADDR = (HOST, PORT)

# Initialize socket
SERVER = socket(AF_INET, SOCK_STREAM)
SERVER.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
SERVER.bind(ADDR)

# Store client data into dictionaries
addresses = {}
positions = {}
status = {}
protocol = ''
if __name__ == '__main__':
    SERVER.listen(5)
    print("Waiting for connection...")
    ACCEPT_THREAD = Thread(target=accept_incoming_connections)
    ACCEPT_THREAD.start()
    ACCEPT_THREAD.join()
    SERVER.close()
