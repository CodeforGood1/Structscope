class PacketHeader {
public:
    int version;
    char type;
    double timestamp;
};

struct CppRecord {
    char flag;
    long long sequence;
    int size;
};

class PrivateData {
    char tag;
    int value;
};

