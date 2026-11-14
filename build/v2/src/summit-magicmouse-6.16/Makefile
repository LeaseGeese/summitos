obj-m := hid-magicmouse.o
KVER ?= $(shell uname -r)
all:
	$(MAKE) -C /lib/modules/$(KVER)/build M=$(CURDIR) modules
clean:
	$(MAKE) -C /lib/modules/$(KVER)/build M=$(CURDIR) clean
