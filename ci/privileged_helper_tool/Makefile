CC=clang
OUTPUT=com.ghltbm.macboxtool.privileged-helper

all: clean release

release: main.m
	$(CC) -framework Foundation -framework Security -arch x86_64 -arch arm64 -mmacosx-version-min=11.0 -o $(OUTPUT) main.m

debug: main.m
	$(CC) -framework Foundation -framework Security -arch x86_64 -arch arm64 -mmacosx-version-min=11.0 -o $(OUTPUT) main.m -DEBUG

clean:
	/bin/rm -f $(OUTPUT)