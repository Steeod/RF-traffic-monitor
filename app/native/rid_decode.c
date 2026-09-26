#include "opendroneid.h"
#include <stdlib.h>
__declspec(dllexport) int rid_decode(const unsigned char *raw, int len, double *out, char *id) {
    if(len!=25 || (raw[0]&15)>2)return -1;
    int type=raw[0]>>4;
    if(type==0) {
        ODID_BasicID_data b;
        if(decodeBasicIDMessage(&b,(const ODID_BasicID_encoded*)raw)!=ODID_SUCCESS)return -1;
        memcpy(id,b.UASID,20);id[20]=0;out[0]=b.IDType;return 0;
    }
    if(type==1) {
        ODID_Location_data l;
        if(decodeLocationMessage(&l,(const ODID_Location_encoded*)raw)!=ODID_SUCCESS)return -1;
        out[0]=l.Latitude;out[1]=l.Longitude;out[2]=l.AltitudeGeo;
        out[3]=l.SpeedHorizontal;out[4]=l.Direction;out[5]=l.TimeStamp;out[6]=l.Status;
        return 1;
    }
    return -1;
}
