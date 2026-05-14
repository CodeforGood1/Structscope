struct TelemetryPacket {
    char tag;
    double timestamp;
    char state;
    void *payload;
    int count;
};

struct CacheSplitDemo {
    char prefix[60];
    int value[2];
};

struct CompactPacket {
    double timestamp;
    void *payload;
    int count;
    char tag;
    char state;
};
