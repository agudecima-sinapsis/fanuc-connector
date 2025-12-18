# Use native compilers for Debian (x86/x86_64)
CC = gcc
CXX = g++

CXXFLAGS = -g -I../src -I../minIni_07 -I. -fPIC
CFLAGS = -g -I../src -I../minIni_07 -I. -fPIC
LDFLAGS = -L. -Wl,-rpath,.
LIBS = -lfwlib32 -lm -lpthread

vpath %.hpp ../src
vpath %.cpp ../src
vpath %.c ../minIni_07

# Source files from fanuc directory
FANUC_SOURCES = FanucAdapter.cpp fanuc_adapter.cpp fanuc_axis.cpp fanuc_path.cpp

# Source files from ../src directory
SRC_SOURCES = adapter.cpp client.cpp condition.cpp device_datum.cpp \
              logger.cpp server.cpp service.cpp string_array.cpp string_buffer.cpp

# Source files from ../minIni_07 directory
MININI_SOURCES = minIni.c

# All source files
ALL_SOURCES = $(FANUC_SOURCES) $(SRC_SOURCES) $(MININI_SOURCES)

# Object files
OBJECTS = $(FANUC_SOURCES:.cpp=.o) $(SRC_SOURCES:.cpp=.o) $(MININI_SOURCES:.c=.o)

all: adapter

adapter: $(OBJECTS) libfwlib32.so libfwlib32.so.1
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o adapter $(OBJECTS) $(LIBS)

# Create symlink chain for library
# libfwlib32.so.1 is needed at runtime
libfwlib32.so.1: libfwlib32-linux-x64.so.1.0.5
	ln -sf libfwlib32-linux-x64.so.1.0.5 libfwlib32.so.1

# libfwlib32.so is needed at link time
libfwlib32.so: libfwlib32.so.1
	ln -sf libfwlib32.so.1 libfwlib32.so

# C++ source files
%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# C source files (minIni.c)
%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# Dependencies for fanuc-specific files
FanucAdapter.o: FanucAdapter.cpp fanuc_adapter.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

fanuc_adapter.o: fanuc_adapter.cpp fanuc_adapter.hpp fanuc_path.hpp fanuc_axis.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

fanuc_axis.o: fanuc_axis.cpp fanuc_axis.hpp fanuc_path.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

fanuc_path.o: fanuc_path.cpp fanuc_path.hpp fanuc_axis.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Dependencies for src files
adapter.o: ../src/adapter.cpp ../src/adapter.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

client.o: ../src/client.cpp ../src/client.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

server.o: ../src/server.cpp ../src/server.hpp ../src/client.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

condition.o: ../src/condition.cpp ../src/condition.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

device_datum.o: ../src/device_datum.cpp ../src/device_datum.hpp ../src/string_buffer.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

logger.o: ../src/logger.cpp ../src/logger.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

service.o: ../src/service.cpp ../src/service.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

string_array.o: ../src/string_array.cpp ../src/string_array.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

string_buffer.o: ../src/string_buffer.cpp ../src/string_buffer.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# minIni.c
minIni.o: ../minIni_07/minIni.c ../minIni_07/minIni.h
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS) adapter libfwlib32.so libfwlib32.so.1

.PHONY: all clean