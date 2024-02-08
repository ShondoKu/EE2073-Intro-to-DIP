# Micropython firmware for STM32F4VE with VScope 1.4r1
# Law Choi Look      ecllaw@ntu.edu.sg          07 Mar 2022
# Wonkeun Chang      wonkeun.chang@ntu.edu.sg   22 Jul 2023

from pyb import Pin
from pyb import ADC
from pyb import DAC
from pyb import USB_VCP
from pyb import Timer

from machine import SPI

from array import array

import micropython
import math

BUFFERSIZE=1000

micropython.alloc_emergency_exception_buf(50) 
usb=USB_VCP()

# Initialize SPI port for control of digital potentiometer of dual DC voltage supply
spi_dc=SPI(sck=Pin('PB13',Pin.OUT),mosi=Pin('PB15',Pin.OUT),miso=Pin('PB14',Pin.IN))
dz=Pin('PB12',Pin.OUT) #dc_voltage set select

# Initialize SPI ports for control of digital potentiometer of ADC buffer amplifiers and input coupling
spi=SPI(sck=Pin('PB3',Pin.OUT),mosi=Pin('PB5',Pin.OUT),miso=Pin('PB4',Pin.IN))
g1=Pin('PD4',Pin.OUT)    # channel 1 gain select
dc1=Pin('PD5',Pin.OUT)   # channel 1 dc_offset select
g2=Pin('PB6',Pin.OUT)    # channel 2 gain select
dc2=Pin('PB7',Pin.OUT)   # channel 2 dc_offset select
c1va0=Pin('PD6',Pin.OUT) # select V/Div # a1a0='00' select s1=DC, '01' select s2=ATT, '10' select s3=AC', '11' select s4=GND
c1va1=Pin('PD7',Pin.OUT) # select channel 1 # s1=0.5V/Div, s2=1V/Div, s3=2V/Div, s4=5V/Div 
c2va0=Pin('PB8',Pin.OUT) # select V/Div
c2va1=Pin('PB9',Pin.OUT) # select channel 2 

# Dual DC voltage supply
def dcsupply(volt):
    y=312-1020/volt
    dz.value(0)
    spi_dc.write(b'\x11')
    spi_dc.write(bytes((int(y),)))
    dz.value(1)

# Arbitrary waveform generator
def agen(ch,freq,typ,amp,os,ns):
    if amp==0: # Use write() instead of write_timed() for DC signal
        dac=DAC(ch,bits=12,buffering=True)
        dac.write(int((4095/330)*os))
    else: # Use write_timed() for time-varying signal
        dac=DAC(ch,bits=12)  # DAC output: ch1 at pin PA4 and ch2 at pin PA5 
        if typ=='sin':
            buf=array('H',[int((4095/330)*(os+amp*math.sin(2*math.pi*i/ns))) for i in range(ns)])
        elif typ=='cos':
            buf=array('H',[int((4095/330)*(os+amp*math.cos(2*math.pi*i/ns))) for i in range(ns)]) 
        elif typ=='saw':
            buf=array('H',[int((4095/330)*(os-amp*(1.0-2.0*i/ns))) for i in range(ns)]) 
        elif typ=='tri':
            k=int(ns/2)
            buf=array('H',[int((4095/330)*(os-amp*(1.0-4.0*i/ns))) for i in range(k)]) 
            buft=array('H',[int((4095/330)*(os+amp*(1.0-4.0*(-0.5+i/ns)))) for i in range(k,ns)])
            buf=buf+buft  
        dac.write_timed(buf,Timer(5+ch,freq=freq*len(buf)),mode=DAC.CIRCULAR)

# Initialize ADC for time based measurements
adc0=ADC('PC0') # pin input = PC0
adc1=ADC('PC1') # pin input = PC1
adc2=ADC('PA2') # pin input = PA2
adc3=ADC('PA3') # pin input = PA3
adc_buf2=array('H',(0 for i in range(BUFFERSIZE))) 
adc_buf3=array('H',(0 for i in range(BUFFERSIZE)))

# Calibration parameters for waveform generators
w1_gain=10.8
w1_dc=179.3 # unit in x10mV 
w2_gain=10.8
w2_dc=179.5 # unit in X10mV

# Initialize DC voltage
dcsupply(5.5)

# Initialize waveform generators output
freq1=1000
freq2=1000
wtype1='sin'
wtype2='sin'
amp1=0
amp2=0
os1=w1_dc
os2=w2_dc
ns1=64
ns2=64
agen(1,freq1,'sin',amp1,os1,ns1)
agen(2,freq2,'sin',amp2,os2,ns2)

while True:
    mode = input()
    if (mode[0:2]=='m1'): # oscilloscope mode; CH1 and CH2 voltage time series 
        fs=int(mode[2:8])
        c1=int(mode[8:9])
        gain1=int(mode[9:12])
        ofs1=int(mode[12:15])
        c2=int(mode[15:16])
        gain2=int(mode[16:19])
        ofs2=int(mode[19:22])
        c1va0.value(c1&(0x1)) # a1a0= '00' DC ; '01' ATT by 20.6 times ; '10' AC ; '11' GND
        c1va1.value((c1&(0x2))>>1)
        c2va0.value(c2&(0x1))
        c2va1.value((c2&(0x2))>>1)
        g1.value(0) # setting ch1 gain 
        spi.write(b'\x11')
        spi.write(bytes((gain1,)))
        g1.value(1) # activate new gain
        dc1.value(0) # setting ch1 dc offset
        spi.write(b'\x11')
        spi.write(bytes((ofs1,)))
        dc1.value(1) # activate new dc offset
        g2.value(0) # setting ch2 gain 
        spi.write(b'\x11')
        spi.write(bytes((gain2,)))
        g2.value(1) # activate new gain
        dc2.value(0) # setting ch2 dc offset
        spi.write(b'\x11')
        spi.write(bytes((ofs2,)))
        dc2.value(1) # activate new dc offset
        adc_samp=Timer(9,freq=fs)
        ADC.read_timed_multi((adc2,adc3),(adc_buf2,adc_buf3),adc_samp)
        usb.write(adc_buf2)
        usb.write(adc_buf3)
    if (mode[0:2]=='m2'):
        v0=adc0.read()
        v1=adc1.read()
        for i in range(9):
            v0+=adc0.read()
            v1+=adc1.read()
        v0/=10
        v1/=10
        usb.write(array('H',[int(v0)]))
        usb.write(array('H',[int(v1)]))
    if (mode[0:2]=='s1'):
        wnum1=int(mode[2:4])
        ns1=int(mode[4:7])
        freq1=int(mode[7:14])
        amp1=int(mode[14:18])
        amp1=amp1/w1_gain
        os1=int(mode[18:])
        os1=-os1/10+w1_dc
        if wnum1==0:
            wtype1='sin'
        elif wnum1==1:
           wtype1='cos'
        elif wnum1==10:
             wtype1='tri'
        elif wnum1==11:
             wtype1='saw'
        else:
             wtype1='none'
        agen(1,freq1,wtype1,amp1,os1,ns1) #output at PA4
        agen(2,freq2,wtype2,amp2,os2,ns2) #output at PA5  # reduce the occurrence of W1/W2 going chaotic
    if (mode[0:2]=='s2'):
        wnum2=int(mode[2:4])
        ns2=int(mode[4:7])
        freq2=int(mode[7:14])
        amp2=int(mode[14:18])
        amp2=amp2/w2_gain 
        os2=int(mode[18:])
        os2=-os2/10+w2_dc
        if wnum2==0:
            wtype2='sin'
        elif wnum2==1:
            wtype2='cos'
        elif wnum2==10:
            wtype2='tri'
        elif wnum2==11:
            wtype2='saw'
        else:
            wtype2='none'
        agen(2,freq2,wtype2,amp2,os2,ns2) #output at PA5
        agen(1,freq1,wtype1,amp1,os1,ns1) #output at PA4 # reduce the occurrence of W1/W2 going chaotic
    if (mode[0:2]=='dz'):
        vV=int(mode[2:6])
        dcsupply(vV/100)
