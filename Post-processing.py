# -*- coding: utf-8 -*-
"""
Created on Tue Oct 30 15:09:12 2018

Post-processing script for 2D Compressible Navier-Stokes solver

rho, rhou, rhov, rhoE numpy array files will be read

Desired:
    -prompts for user to define working directory; similar to batch file:
        :Directories
        echo Directories...
        dir /b /a:d
        set locDir=""
        set /p locDir=What local directory to establish connection with?
        IF %locDir%=="" (GOTO Connect)
        cd %locDir%
        echo.
        GOTO Directories
    -prompt user for input file destination for converting conservative to 
    primitive variables
    -display data available
    -user selects time and data to start displaying
    -user inputs f or b to specify going ahead in time or backwards
    -standalone script to pass in directory and automate??? use sys package

@author: Joseph
"""

import numpy as np
#import CoolProp.CoolProp as CP
import os
import sys
import string as st
from matplotlib import pyplot, cm
from mpl_toolkits.mplot3d import Axes3D

pyplot.ioff()

# Recursive walk through directory tree with user inputs
def get_Directory():
    places=os.walk(os.getcwd())
    
    files_present=None
    contin='n'
    while contin!='':
        for root, dirs, files in places:
            print root
#            proc=raw_input('Cycle through directories <y> or type destination <n>?')
            for i in range(len(dirs)):
                print dirs[i]
            while True:
                try:
                    contin=raw_input('Enter sub-directory>')
                    os.chdir(contin)
                    j=0
                    if contin in dirs:
                        while len(dirs)>1:
                            if dirs[j]==contin:
                                j+=1
                            else:
                                del dirs[j]
                    else:
                        contin='..'
                    break
                except WindowsError:
                    if contin=='':
                        break
                    else:
                        print 'Directory does not exist'
            
            if contin=='..':
                places=os.walk(os.getcwd())
                break
            elif contin=='':
                files_present=files
                break
    
    return files_present

# Eliminate files without a given extension from a list
def process_Files(files, ext):
    i,f_len=0,len(files)
    while i<f_len:
        if st.find(files[i], ext)<0:
            del files[i]
            f_len-=1
        else:
            i+=1

# Load numpy array files before/after a given time
def load_Data(files, time, isBefore):
    # Look to time stamps
    time_next=time
    time_diff=1e10
    for i in range(len(files)):
        if files[i]=='X.npy' or files[i]=='Y.npy':
            continue
        time_prev=float(st.split(st.split(files[i],'_')[1], '.npy')[0])
        if isBefore:
            if time_prev<time and time-time_prev<time_diff \
            and time-time_prev>0:
                time_next=time_prev
                time_diff=time-time_next
        else:
            if time_prev>time and time_prev-time<time_diff \
            and time_prev-time>0:
                time_next=time_prev
                time_diff=time_next-time
#    print(time_next)
    if time_next<=1e-9:
#        print 'Time is 0'
        rho=np.load('rho_0.000000.npy', False)
        rhou=np.load('rhou_0.000000.npy', False)
        rhov=np.load('rhov_0.000000.npy', False)
        rhoE=np.load('rhoE_0.000000.npy', False)
    else:
#        print 'Time is nonzero'
        rho=np.load('rho_'+'%.6f'%(time_next)+'.npy', False)
        rhou=np.load('rhou_'+'%.6f'%(time_next)+'.npy', False)
        rhov=np.load('rhov_'+'%.6f'%(time_next)+'.npy', False)
        rhoE=np.load('rhoE_'+'%.6f'%(time_next)+'.npy', False)
    
    return time_next, rho, rhou, rhov, rhoE

print('######################################################')
print('#            2D Conduction Post-processing           #')
print('#              Created by J. Mark Epps               #')
print('#          Part of Masters Thesis at UW 2018-2020    #')
print('######################################################\n')

inputargs=sys.argv
if len(inputargs)>1:
    dir_files=inputargs[1]

try:
    os.chdir(dir_files)
except:
    sys.exit('Directory "'+dir_files+'" not found')
# Get Arrhenius parameters
A0=-1.0
Ea=-1.0
source='False'
input_file=open('Input_file.txt')
while A0<0 or Ea<0 or source=='False':
    line=input_file.readline()
    if st.find(line, 'Ea')==0:
        Ea=float(st.split(line, ':')[1])
    elif st.find(line, 'A0')==0:
        A0=float(st.split(line, ':')[1])
    elif st.find(line, 'Source_Kim')==0:
        source=st.split(line, ':')[1]
input_file.close()
#print 'Ea=%f, A0=%f'%(Ea,A0)

# Get times to process
times=os.listdir('.')
i=len(times)
j=0
while i>j:
    if st.find(times[j],'T')==0 and st.find(times[j],'.npy')>0:
        times[j]=st.split(st.split(times[j],'_')[1],'.npy')[0]
        j+=1
    else:
        del times[j]
        i-=1

# Generate graphs
for time in times:
    X=np.load('X.npy', False)
    Y=np.load('Y.npy', False)
    T=np.load('T_'+time+'.npy', False)
    if st.find(source,'True')>=0:
        eta=np.load('eta_'+time+'.npy', False)
    
    
    # Temperature contour
    fig=pyplot.figure(figsize=(6, 6))
    pyplot.contourf(X, Y, T, alpha=0.5, cmap=cm.viridis)#, vmin=270, vmax=2000)  
    pyplot.colorbar()
    pyplot.xlabel('$x$ (m)')
    pyplot.ylabel('$y$ (m)')
#    pyplot.clim(270, 2000)
    pyplot.title('Temperature distribution t='+time);
    fig.savefig('T_'+time+'.png',dpi=300)
    pyplot.close(fig)
    
    if st.find(source,'True')>=0:
        # Progress contour
        fig=pyplot.figure(figsize=(6, 6))
        pyplot.contourf(X, Y, eta, alpha=0.5, cmap=cm.viridis)#, vmin=0.0, vmax=1.0)  
        pyplot.colorbar()
        pyplot.xlabel('$x$ (m)')
        pyplot.ylabel('$y$ (m)')
    #    pyplot.clim(0.0, 1.0)
        pyplot.title('Progress distribution t='+time);
        fig.savefig('eta_'+time+'.png',dpi=300)
        pyplot.close(fig)
        
        # Reaction rate contour
        fig=pyplot.figure(figsize=(6, 6))
        pyplot.contourf(X, Y, A0*(1-eta)*np.exp(-Ea/8.314/T), alpha=0.5, cmap=cm.viridis)#, vmin=0.0, vmax=1.0)  
        pyplot.colorbar(format='%.2e')
        pyplot.xlabel('$x$ (m)')
        pyplot.ylabel('$y$ (m)')
    #    pyplot.clim(0.0, 1.0)
        pyplot.title('Reaction rate t='+time);
        fig.savefig('Phi_'+time+'.png',dpi=300)
        pyplot.close(fig)
    
    print 'Processed '+time

##########################################################################
# ------------------------------------- Get input file parameters
##########################################################################
#print '***********Where is the input file from the simulation?**************'
#files_present=get_Directory()
#
#process_Files(files_present,'txt')


#for i in range(len(files_present)):
#    print files_present[i]
#
#while True:
#    try:
#        input_file=raw_input('Which file is it?')
#        fin=open(input_file, 'r')
#        break
#    except:
#        try:
#            input_file+='.txt'
#            fin=open(input_file, 'r')
#            break
#        except:
#            print 'File does not exist'

#while gamma==0 or R==0:
#    read=fin.readline()
#    # [IN PROGRESS] calculate gamma and R based on fluid
##    if st.find(read, 'Fluid')>=0:
##        fl=st.split(read, ':')[1]
##        gamma=CP.PropsSI('Cpmass','T',300,'P',101325,fl)/CP.PropsSI('Cvmass','T',300,'P',101325,fl)
##        R = CP.PropsSI('gas_constant','Air')/CP.PropsSI('M',fl) # Specific to fluid
#    if st.find(read, 'gamma')==0:
#        gamma=float(st.split(read, ':')[1])
#    if st.find(read, 'R:')==0:
#        R=float(st.split(read, ':')[1])
#fin.close()
#print 'gamma=%f and R=%f'%(gamma,R)
#print '############################################'
##########################################################################
# -------------------------------------Get array data files
##########################################################################
#print '*****************Where are the numpy data files?********************'
#print 'Starting directory: '+os.getcwd()
#files_present=get_Directory()
#
#process_Files(files_present, 'npy')
#
#for i in range(len(files_present)):
#    print files_present[i]
#
#while True:
#    data=raw_input('Which file to start with?')
#    if data in files_present:
#        break
##    elif st.find(data, '.npy')<0:
##        data+='.npy'
##        if data in files_present:
##            break
##        else:
##            files_present=st.split(files_present, '_')[1]
##            if data in files_present:
##                break
##            else:    
##                print 'File does not exist'
#    else:
#        print 'File does not exist'

#time0=float(st.split(st.split(data,'_')[1], '.npy')[0])
#try:
#    X=np.load('X.npy', False)
#except:
#    sys.exit('Coordinate arrays not in this directory')
#Y=np.load('Y.npy', False)
##rho=np.load('rho_'+str(time0)+'.npy', False)
##rhou=np.load('rhou_'+str(time0)+'.npy', False)
##rhov=np.load('rhov_'+str(time0)+'.npy', False)
##rhoE=np.load('rhoE_'+str(time0)+'.npy', False)
#usr_inp='y'
#isPrev=True
#while usr_inp!='exit':
#    
#    time0, rho, rhou, rhov, rhoE=load_Data(files_present, time0, isPrev)
#    
#    # 1D Plot
##    fig2=pyplot.figure(figsize=(7,7))
##    pyplot.plot(Y[:,1]*1000, T[:,1],marker='x')
##    pyplot.xlabel('$y$ (mm)')
##    pyplot.ylabel('T (K)')
##    pyplot.title('Temperature distribution at 2nd x')
##    pyplot.xlim(5,6);
#    #fig2.savefig('Plot2.png',dpi=300)
#    
#    # Velocity Quiver plot and pressure contour
#    print 'Time: %.6f'%time0
#    pl=5
#    fig3=pyplot.figure(figsize=(7, 7))
#    pyplot.quiver(X[::pl, ::pl], Y[::pl, ::pl], \
#                  u[::pl, ::pl], v[::pl, ::pl]) 
#    pyplot.contourf(X, Y, T, alpha=0.5, cmap=cm.viridis)  
#    pyplot.colorbar()
#    pyplot.xlabel('$x$ (m)')
#    pyplot.ylabel('$y$ (m)')
#    pyplot.title('Velocity plot and Temperature contours');
#    pyplot.show()
##    fig3.savefig('%.6f_Vel_Temp.png'%time0,dpi=300)
#    # 
#    ## Temperature contour
#    #fig4=pyplot.figure(figsize=(7, 7))
#    #pyplot.contourf(X, Y, T, alpha=0.5, cmap=cm.viridis)  
#    #pyplot.colorbar()
#    #pyplot.xlabel('$x$ (m)')
#    #pyplot.ylabel('$y$ (m)')
#    #pyplot.title('Temperature distribution');
#    ##fig4.savefig(datTime+'_Temp.png',dpi=300)
#    #
#    ## Density contour
#    #fig5=pyplot.figure(figsize=(7, 7))
#    #pyplot.contourf(X, Y, rho, alpha=0.5, cmap=cm.viridis)  
#    #pyplot.colorbar()
#    #pyplot.xlabel('$x$ (m)')
#    #pyplot.ylabel('$y$ (m)')
#    #pyplot.title('Density distribution');
#    #fig4.savefig(datTime+'_Temp.png',dpi=300)
#    
#    usr_inp=raw_input('Next, Prev, exit>')
#    if usr_inp=='Next' or usr_inp=='next':
#        isPrev=False
##    elif usr_inp=='change':
##        
#    else:
#        isPrev=True
#        
#pyplot.show()