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
import copy
from mpi4py import MPI

import GeomClasses as Geom
import SolverClasses as Solvers
import FileClasses
import mpi_routines

##########################################################################
# -------------------------------------Beginning
##########################################################################

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

# Print intro on process 0 only
if rank==0:
    print('######################################################')
    print('#             2D Heat Conduction Solver              #')
    print('#              Created by J. Mark Epps               #')
    print('#          Part of Masters Thesis at UW 2018-2020    #')
    print('######################################################\n')
    
    # Start timer
    time_begin=time.time()

# Get arguments to script execution
settings={'MPI_Processes': size}
BCs={}
Sources={}
Species={}
inputargs=sys.argv
if len(inputargs)>2:
    input_file=inputargs[1]
    settings['Output_directory']=inputargs[2]
else:
    if rank==0:
        print 'Usage is: python main.py [Input file] [Output directory]\n'
        print 'where\n'
        print '[Input file] is the name of the input file with extension; must be in current directory'
        print '[Output directory] is the directory to output the data; will create relative to current directory if it does not exist'
        print '***********************************'
    sys.exit('Solver shut down on %i'%(rank))
##########################################################################
# -------------------------------------Read input file
##########################################################################
if rank==0:
    print 'Reading input file...'
fin=FileClasses.FileIn(input_file, 0)
fin.Read_Input(settings, Sources, Species, BCs)
comm.Barrier()
try:
    os.chdir(settings['Output_directory'])
except:
    comm.Barrier()
    if rank==0:
        os.makedirs(settings['Output_directory'])
    comm.Barrier()
    os.chdir(settings['Output_directory'])

##########################################################################
# -------------------------------------Initialize solver and domain
##########################################################################
if rank==0:
    print '################################'
    print 'Initializing geometry package...'
domain=Geom.TwoDimDomain(settings, Species, settings['Domain'], rank)
domain.mesh()
hx,hy=domain.CV_dim()
if rank==0:
    print '################################'
    print 'Initializing MPI and solver...'
    np.save('X', domain.X, False)
    np.save('Y', domain.Y, False)
mpi=mpi_routines.MPI_comms(comm, rank, size, Sources, Species)
err=mpi.MPI_discretize(domain)
if err>0:
    sys.exit('Problem discretizing domain into processes')
hx=mpi.split_var(hx, domain)
hy=mpi.split_var(hy, domain)
#print '****Rank: %i, X array: %f, %f'%(rank, np.amin(domain.X[0,:]), np.amax(domain.X[0,:]))
#print '****Rank: %i, X array shape:  '%(rank)+str(np.shape(domain.X))
#print '****Rank: %i, Y array: %f, %f'%(rank, np.amin(domain.Y[:,0]), np.amax(domain.Y[:,0]))
#print '****Rank: %i, Process neighbors(LRTB): %i, %i, %i, %i'%(rank, domain.proc_left, domain.proc_right, domain.proc_top, domain.proc_bottom)
#print '****Rank: %i, vol/Area shapes: '%(rank)+str(vol.shape)+', '+str(Ax_l.shape)+', '+str(Ax_r.shape)
#print '****Rank: %i, process arrangemtn: '%(rank)+str(domain.proc_arrang)
domain.create_var(Species)
solver=Solvers.TwoDimSolver(domain, settings, Sources, copy.deepcopy(BCs), comm)
if rank==0:
    settings['MPI_arrangment']=domain.proc_arrang.copy()
    print '################################'
    print 'Initializing domain...'

time_max='0.000000'
T=settings['Temperature_IC']*np.ones_like(domain.E)
# Restart from previous data
if st.find(settings['Restart'], 'None')<0:
    times=os.listdir('.')
    i=len(times)
    j=0
    while i>j:
        if st.find(times[j],'T')==0 and st.find(times[j],'.npy')>0 \
            and st.find(times[j],str(settings['Restart']))>=0:
            times[j]=st.split(st.split(times[j],'_')[1],'.npy')[0]
#            if st.find(times[j],str(settings['Restart']))>=0:
            time_max=times[j]
            j+=1
            break
        else:
            del times[j]
            i-=1
    if time_max=='0.000000':
        sys.exit('Cannot find a file to restart a simulation with')
    
    T=np.load('T_'+time_max+'.npy')
    T=mpi.split_var(T, domain)
    if st.find(Sources['Source_Kim'],'True')>=0:
        eta=np.load('eta_'+time_max+'.npy')
        domain.eta=mpi.split_var(eta, domain)
        del eta
    if domain.model=='Species':
        P=np.load('P_'+time_max+'.npy')
        domain.P=mpi.split_var(P, domain)
        species=['g','s']
        for i in range(len(species)):
            rho_species=np.load('rho_'+species[i]+'_'+time_max+'.npy')
            domain.rho_species[species[i]]=mpi.split_var(rho_species, domain)
        del rho_species, P
            
#if (bool(domain.rho_species)) and (st.find(settings['Restart'], 'None')>=0):
#    for i in range(len(Species['Species'])):
##        domain.rho_species[Species['Species'][i]][:,:]=Species['Specie_IC'][i]
#        domain.rho_species[Species['Species'][i]][:,:]=Species['Specie_IC'][i]
#        domain.rho_0+=domain.rho_species[Species['Species'][i]] 
rhoC=domain.calcProp(T_guess=T, init=True)
domain.E=rhoC*T
del rhoC,T
##########################################################################
# ------------------------Write Input File settings to output directory
##########################################################################
if rank==0:
    print '################################'
    print 'Saving input file to output directory...'
    #datTime=str(datetime.date(datetime.now()))+'_'+'{:%H%M}'.format(datetime.time(datetime.now()))
    isBinFile=False
    
    input_file=FileClasses.FileOut('Input_file', isBinFile)
    
    # Write header to file
    input_file.header_cond('INPUT')
    
    # Write input file with settings
    input_file.input_writer_cond(settings, Sources, Species, BCs)
    input_file.close()
    print '################################\n'
    
    print 'Saving data to numpy array files...'
#print '****Rank: %i, first save to numpy files'%(rank)
mpi.save_data(domain, Sources, Species, time_max)

##########################################################################
# -------------------------------------Solve
##########################################################################
t,nt,tign=float(time_max)/1000,0,0 # time, number steps and ignition time initializations
v_0,v_1,v,N=0,0,0,0 # combustion wave speed variables initialization
dy=mpi.compile_var(domain.dY, domain)

# Setup intervals to save data
output_data_t,output_data_nt=0,0
if settings['total_time_steps']=='None':
    output_data_t=settings['total_time']/settings['Number_Data_Output']
    settings['total_time_steps']=settings['total_time']*10**12
    t_inc=int(t/output_data_t)+1
elif settings['total_time']=='None':
    output_data_nt=int(settings['total_time_steps']/settings['Number_Data_Output'])
    settings['total_time']=settings['total_time_steps']*10**12
    t_inc=0

# Ignition conditions
ign,ign_0=0,0

if rank==0:
    print 'Solving:'
while nt<settings['total_time_steps'] and t<settings['total_time']:
    # First point in calculating combustion propagation speed
    if st.find(Sources['Source_Kim'],'True')>=0 and ign==1:
        eta=mpi.compile_var(domain.eta, domain)
        if rank==0:
            if st.find(settings['Domain'], 'Axisymmetric')>=0:
                v_0=np.sum(eta[:,0]*dy[:,0])
            else:
                v_0=np.sum(eta[:,int(len(eta[0,:])/2)]*dy[:,int(len(eta[0,:])/2)])
    
    # Update ghost nodes
    mpi.update_ghosts(domain)
    # Actual solve
    err,dt,ign=solver.Advance_Soln_Cond(nt, t, hx, hy, ign)
    t+=dt
    nt+=1
    # Check all error codes and send the maximum code to all processes
    err=comm.reduce(err, op=MPI.MAX, root=0)
    err=comm.bcast(err, root=0)
    ign_0=ign
    # Check all ignition codes and send maximum
    ign_0=comm.reduce(ign_0, op=MPI.MIN, root=0)
    ign_0=comm.bcast(ign_0, root=0)
    ign=comm.reduce(ign, op=MPI.MAX, root=0)
    ign=comm.bcast(ign, root=0)
    
    if err>0:
        if rank==0:
            input_file=open('Input_file.txt', 'a')
            print '#################### Solver aborted #######################'
            print '################### Error code %i'%(err)
            print 'Error codes: 1-time step, 2-Energy, 3-reaction progress, 4-Species balance'
            print 'Saving data to numpy array files...'
            input_file.write('#################### Solver aborted #######################\n')
            input_file.write('Time step %i, Time elapsed=%f, error code=%i;\n'%(nt,t,err))
            input_file.write('Error codes: 1-time step, 2-Energy, 3-reaction progress, 4-Species balance\n')
            input_file.close()
        mpi.save_data(domain, Sources, Species, '{:f}'.format(t*1000))
        break
    
    # Change boundary conditions if ignition occurs
    if ign==1 and ign_0==0:
        if domain.proc_top<0:
            solver.BCs.BCs['bc_north_E']=BCs['bc_right_E']
        if rank==0:
	    print 'Ignition occurred at t=%f ms'%(t*1000)
            input_file=open('Input_file.txt', 'a')
            input_file.write('##bc_north_E_new:')
            input_file.write(str(BCs['bc_right_E'])+'\n')
            input_file.close()
            tign=t
        mpi.save_data(domain, Sources, Species, '{:f}'.format(t*1000))
        
    # Second point in calculating combustion propagation speed
    if st.find(Sources['Source_Kim'],'True')>=0 and ign==1 and ign_0==1:
        eta=mpi.compile_var(domain.eta, domain)
        if rank==0:
            if st.find(settings['Domain'], 'Axisymmetric')>=0:
                v_1=np.sum(eta[:,0]*dy[:,0])
            else:
                v_1=np.sum(eta[:,int(len(eta[0,:])/2)]*dy[:,int(len(eta[0,:])/2)])
            if (v_1-v_0)/dt>0.01:
                v+=(v_1-v_0)/dt
                N+=1
    
    # Output data to numpy files
    if (output_data_nt!=0 and nt%output_data_nt==0) or \
        (output_data_t!=0 and (t>=output_data_t*t_inc and t-dt<output_data_t*t_inc)):
        if rank==0:
            print 'Saving data to numpy array files...'
            input_file=open('Input_file.txt', 'a')
            try:
                input_file.write('Wave speed [m/s] at t=%f ms: inst-%.2f, avg-%.2f\n'%(t*1000, (v_1-v_0)/dt, v/N))
            except:
                input_file.write('Wave speed [m/s] at t=%f ms: 0 m/s\n'%(t*1000))
            input_file.close()
        mpi.save_data(domain, Sources, Species, '{:f}'.format(t*1000))
        t_inc+=1
        
if rank==0:
    time_end=time.time()
    input_file=open('Input_file.txt', 'a')
    input_file.write('Final time step size: %f microseconds\n'%(dt*10**6))
    print 'Ignition time: %f ms'%(tign*1000)
    input_file.write('Ignition time: %f ms\n'%(tign*1000))
    print 'Solver time per 1000 time steps: %f min'%((time_end-time_begin)/60.0*1000/nt)
    input_file.write('Solver time per 1000 time steps: %f min\n'%((time_end-time_begin)/60.0*1000/nt))
    print 'Number of time steps completed: %i'%(nt)
    input_file.write('Number of time steps completed: %i\n'%(nt))
    try:
        print 'Average wave speed: %.2f m/s'%(v/N)
        input_file.write('Average wave speed: %.2f m/s\n'%(v/N))
        input_file.close()
    except:
        print 'Average wave speed: 0 m/s'
        input_file.write('Average wave speed: 0 m/s\n')
        input_file.close()
    print('Solver has finished its run')
