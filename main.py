# -*- coding: utf-8 -*-
"""
######################################################
#             2D Heat Conduction Solver              #
#              Created by J. Mark Epps               #
#          Part of Masters Thesis at UW 2018-2020    #
######################################################

This file contains the main executable script for solving 2D conduction:
    -Uses FileClasses.py to read and write input files to get settings for solver
    and geometry
    -Creates a domain class from GeomClasses.py
    -Creates solver class from SolverClasses.py with reference to domain class
    -Can be called from command line with: 
        python main.py [Input file name+extension] [Output directory relative to current directory]
    -Calculates the time taken to run solver
    -Changes boundary conditions based on ignition criteria
    -Saves temperature data (.npy) at intervals defined in input file
    -Saves x,y meshgrid arrays (.npy) to output directory

Features:
    -Ignition condition met, will change north BC to that of right BC
    -Saves temperature and reaction data (.npy) depending on input file 
    settings

"""

##########################################################################
# ----------------------------------Libraries and classes
##########################################################################
import numpy as np
import string as st
#from datetime import datetime
import os
import sys
import time

from GeomClasses import TwoDimPlanar as TwoDimPlanar
import SolverClasses as Solvers
import FileClasses

def save_data(Domain, Sources, time):
    T=Domain.TempFromConserv()
    np.save('T_'+time, T, False)
    if st.find(Sources['Source_Kim'],'True')>=0:
        np.save('eta_'+time, Domain.eta, False)
#        for i in range(len(Domain.Y_species[0,0,:])):
#            np.save('Y_'+str(i)+'_'+time, Domain.Y_species[:,:,i], False)

print('######################################################')
print('#             2D Heat Conduction Solver              #')
print('#              Created by J. Mark Epps               #')
print('#          Part of Masters Thesis at UW 2018-2020    #')
print('######################################################\n')

# Start timer
time_begin=time.time()

# Get arguments to script execution
settings={}
BCs={}
Sources={}
inputargs=sys.argv
if len(inputargs)>2:
    input_file=inputargs[1]
    settings['Output_directory']=inputargs[2]
else:
    print 'Usage is: python main.py [Input file] [Output directory]\n'
    print 'where\n'
    print '[Input file] is the name of the input file with extension; must be in current directory'
    print '[Output directory] is the directory to output the data; will create relative to current directory if it does not exist'
    print '***********************************'
    sys.exit('Solver not started')
##########################################################################
# -------------------------------------Read input file
##########################################################################
print 'Reading input file...'
fin=FileClasses.FileIn(input_file, 0)
fin.Read_Input(settings, Sources, BCs)
try:
    os.chdir(settings['Output_directory'])
except:
    os.makedirs(settings['Output_directory'])
    os.chdir(settings['Output_directory'])

print '################################'

# Initial conditions from previous run/already in memory
#Use_inital_values                   = False


print 'Initializing geometry package...'
domain=TwoDimPlanar(settings, 'Solid')
domain.mesh()
print '################################'

##########################################################################
# -------------------------------------Initialize solver and domain
##########################################################################

print 'Initializing solver package...'
solver=Solvers.TwoDimPlanarSolve(domain, settings, Sources, BCs, 'Solid')
print '################################'

print 'Initializing domain...'
k,rho,Cv=domain.calcProp()
domain.E[:,:]=rho*Cv*domain.CV_vol()*300
del k,rho,Cv
domain.Y_species[:,:,0]=2.0/5
domain.Y_species[:,:,1]=3.0/5
print '################################'
##########################################################################
# ------------------------Write Input File settings to output directory
##########################################################################
print 'Saving input file to output directory...'
#datTime=str(datetime.date(datetime.now()))+'_'+'{:%H%M}'.format(datetime.time(datetime.now()))
isBinFile=False

input_file=FileClasses.FileOut('Input_file', isBinFile)

# Write header to file
input_file.header_cond('INPUT')

# Write input file with settings
input_file.input_writer_cond(settings, Sources, BCs)
print '################################\n'

print 'Saving data to numpy array files...'
save_data(domain, Sources, '0.000000')
np.save('X', domain.X, False)
np.save('Y', domain.Y, False)

##########################################################################
# -------------------------------------Solve
##########################################################################
t,nt,tign=0,0,0 # time, number steps and ignition time initializations
v_0,v_1,v,N=0,0,0,0 #combustion wave speed variables initialization
output_data_t,output_data_nt=0,0
if settings['total_time_steps']=='None':
    settings['total_time_steps']=settings['total_time']*10**9
    output_data_t=settings['total_time']/settings['Number_Data_Output']
elif settings['total_time']=='None':
    settings['total_time']=settings['total_time_steps']*10**9
    output_data_nt=int(settings['total_time_steps']/settings['Number_Data_Output'])
Sources['Ignition']=st.split(Sources['Ignition'], ',')
Sources['Ignition'][1]=float(Sources['Ignition'][1])
BCs_changed=False

print 'Solving:'
while nt<settings['total_time_steps'] and t<settings['total_time']:
    # First point in calculating combustion propagation speed
    T_0=domain.TempFromConserv()
    if st.find(Sources['Source_Kim'],'True')>=0 and BCs_changed:
#        v_0=np.sum(domain.eta[:,int(len(domain.eta[0,:])/2)]*domain.dy)
        v_0=np.sum(domain.eta*solver.dy)/len(domain.eta[0,:])
    err,dt=solver.Advance_Soln_Cond(nt, t)
    t+=dt
    nt+=1
    if err==1:
        print '#################### Solver aborted #######################'
        print 'Saving data to numpy array files...'
        save_data(domain, Sources, '{:f}'.format(t))
        break
    
    # Output data to numpy files
    if output_data_nt!=0 and nt%output_data_nt==0:
        print 'Saving data to numpy array files...'
        save_data(domain, Sources, '{:f}'.format(t))
        
    # Change boundary conditions
    T=domain.TempFromConserv()
    if ((Sources['Ignition'][0]=='eta' and np.amax(domain.eta)>=Sources['Ignition'][1])\
        or (Sources['Ignition'][0]=='Temp' and np.amax(T)>=Sources['Ignition'][1]))\
        and not BCs_changed:
        solver.BCs['bc_north']=solver.BCs['bc_right']
        BCs_changed=True
        tign=t
        save_data(domain, Sources, '{:f}'.format(t))
#    if not BCs_changed:
#        k,rho,Cv=domain.calcProp()
#        T_theo=300+2*solver.BCs['bc_north'][1]/k[-1,0]\
#            *np.sqrt(k[-1,0]/rho[-1,0]/Cv[-1,0]*t/np.pi)
#        dT_theo=solver.BCs['bc_north'][1]/k[-1,0]\
#            *np.sqrt(k[-1,0]/rho[-1,0]/Cv[-1,0]/np.pi/t)
##        if (T_theo-T[-1,0])/T_theo<-0.3:
#        if (dT_theo-((T[-1,0]-T_0[-1,0])/dt))/dT_theo<-1.0:
#            solver.BCs['bc_north']=solver.BCs['bc_right']
#            BCs_changed=True
#            tign=t
#            save_data(domain, Sources, '{:f}'.format(t))
    
    # Second point in calculating combustion propagation speed
    if st.find(Sources['Source_Kim'],'True')>=0 and BCs_changed:
#        v_1=np.sum(domain.eta[:,int(len(domain.eta[0,:])/2)]*domain.dy)
        v_1=np.sum(domain.eta*solver.dy)/len(domain.eta[0,:])
        if (v_1-v_0)/dt>0.001:
            v+=(v_1-v_0)/dt
            N+=1
        
time_end=time.time()
print 'Ignition time: %f ms'%(tign*1000)
input_file.Write_single_line('Ignition time: %f ms'%(tign*1000))
print 'Solver time per 1000 time steps: %f min'%((time_end-time_begin)/60.0*1000/nt)
input_file.Write_single_line('Solver time per 1000 time steps: %f min'%((time_end-time_begin)/60.0*1000/nt))
try:
    print 'Average wave speed: %f m/s'%(v/N)
    input_file.Write_single_line('Average wave speed: %f m/s'%(v/N))
    input_file.close()
except:
    print 'Average wave speed: 0 m/s'
    input_file.Write_single_line('Average wave speed: 0 m/s')
    input_file.close()

print('Solver has finished its run')