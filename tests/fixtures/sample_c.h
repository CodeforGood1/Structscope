struct FourByteFields {
    int a;
    int b;
    float c;
};

struct MixedPadding {
    char tag;
    double value;
    char state;
    long long count;
};

struct Point {
    int x;
    int y;
};

struct NestedMember {
    char kind;
    struct Point origin;
    double weight;
};

struct BitFieldFlags {
    unsigned int ready : 1;
    unsigned int mode : 3;
    unsigned int count;
};

typedef struct AliasStruct {
    char code;
    int id;
    double score;
} AliasStruct;

