# -*- coding: utf-8 -*-
"""
######################################################
#             2D Heat Conduction Solver              #
#              Created by J. Mark Epps               #
#          Part of Masters Thesis at UW 2018-2020    #
######################################################

This file contains the solver classes for 2D planar and axisymmetric 
Heat Conduction:
    -Modifies geometry class variables directly
    -Calculate time step based on Fourier number
    -Compute conduction equations
    -Add source terms as needed
    -Applies boundary conditions (can vary along a side)

Features/assumptions:
    -time step based on Fourrier number and local discretizations in x and y
    -equal node spacing in x or y
    -thermal properties can vary in space (call from geometry object)
    -Radiation boundary conditions

"""

import numpy as np
import copy
import string as st
import Source_Comb
import BCClasses
from mpi4py import MPI

# 2D solver (Cartesian coordinates)
class TwoDimSolver():
    def __init__(self, geom_obj, settings, Sources, BCs, comm):
        self.Domain=geom_obj # Geometry object
        self.time_scheme=settings['Time_Scheme']
        self.dx,self.dy=geom_obj.dX,geom_obj.dY
        self.Fo=settings['Fo']
        self.CFL=settings['CFL']
        self.dt=settings['dt']
        self.conv=settings['Convergence']
        self.countmax=settings['Max_iterations']
        self.comm=comm
        self.diff_inter=settings['diff_interpolation']
        self.conv_inter=settings['conv_interpolation']
        
        # Define source terms and pointer to source object here
        self.get_source=Source_Comb.Source_terms(Sources['Ea'], Sources['A0'], Sources['dH'], Sources['gas_gen'])
        self.source_unif=Sources['Source_Uniform']
        self.source_Kim=Sources['Source_Kim']
        self.ign=st.split(Sources['Ignition'], ',')
        self.ign[0]=int(self.ign[0])
        self.ign[1]=int(self.ign[1])
        
        # BC class
        self.BCs=BCClasses.BCs(BCs, self.dx, self.dy, settings['Domain'])
        self.BCs.X=geom_obj.X
        # Ensure proper BCs for this process
        self.mult_BCs(BCs)
    
    # Modify BCs based on processes next to current one AND if multiple
    # BCs are specified on a given boundary
    def mult_BCs(self, BC_global):
        # Left boundary
        if self.Domain.proc_left>=0:
            self.BCs.BCs['bc_left_E']=['F', 0.0, (0, -1)]
            self.BCs.BCs['bc_left_rad']='None'
            self.BCs.BCs['bc_left_P']=['none', 0.0, (0, -1)]
        # Global boundary with multiple BCs
        elif len(BC_global['bc_left_E'])>3:
            i=len(BC_global['bc_left_E'])/3
            j=0
            while i>j:
                # Lower bound of BC in this process
                if BC_global['bc_left_E'][2+3*j][0]>=self.Domain.proc_row*self.Domain.Ny\
                    and BC_global['bc_left_E'][2+3*j][0]<(self.Domain.proc_row+1)*self.Domain.Ny:
                    st=BC_global['bc_left_E'][2+3*j][0]-self.Domain.proc_row*self.Domain.Ny
                    # upper bound of BC in this process
                    if BC_global['bc_left_E'][2+3*j][1]<=(self.Domain.proc_row+1)*self.Domain.Ny:
                        en=BC_global['bc_left_E'][2+3*j][1]-self.Domain.proc_row*self.Domain.Ny
                    # upper bound outside this process
                    else:
                        en=self.Domain.Ny
                    # Ghost node on bottom
                    if self.Domain.proc_bottom>=0:
                        st+=1
                        en+=1
                    elif self.Domain.proc_top<0:
                        en+=1
                    self.BCs.BCs['bc_left_E'][2+3*j]=(st,en)
                    j+=1
                # Lower bound of BC not in this process, but upper bound is
                elif BC_global['bc_left_E'][2+3*j][1]<=(self.Domain.proc_row+1)*self.Domain.Ny\
                    and BC_global['bc_left_E'][2+3*j][1]>self.Domain.proc_row*self.Domain.Ny:
                    st=0
                    en=BC_global['bc_left_E'][2+3*j][1]-self.Domain.proc_row*self.Domain.Ny
                    # Ghost node on bottom
                    if self.Domain.proc_bottom>=0:
                        st+=1
                        en+=1
                    elif self.Domain.proc_top<0:
                        en+=1
                    self.BCs.BCs['bc_left_E'][2+3*j]=(st,en)
                    j+=1
                    
                # Process lies inside the upper and lower bounds (are outside process)
                elif BC_global['bc_left_E'][2+3*j][0]<self.Domain.proc_row*self.Domain.Ny\
                    and BC_global['bc_left_E'][2+3*j][1]>(self.Domain.proc_row+1)*self.Domain.Ny:
                    self.BCs.BCs['bc_left_E'][2+3*j]=(0,-1)
                    j+=1
                # BC has no effect on this process
                else:
                    del self.BCs.BCs['bc_left_E'][3*j:3+3*j]
                    i-=1

        # Right boundary
        if self.Domain.proc_right>=0:
            self.BCs.BCs['bc_right_E']=['F', 0.0, (0, -1)]
            self.BCs.BCs['bc_right_rad']='None'
            self.BCs.BCs['bc_right_P']=['none', 0.0, (0, -1)]
        # Global boundary with multiple BCs
        elif len(BC_global['bc_right_E'])>3:
            i=len(BC_global['bc_right_E'])/3
            j=0
            while i>j:
                # Lower bound of BC in this process
                if BC_global['bc_right_E'][2+3*j][0]>=self.Domain.proc_row*self.Domain.Ny\
                    and BC_global['bc_right_E'][2+3*j][0]<(self.Domain.proc_row+1)*self.Domain.Ny:
                    st=BC_global['bc_right_E'][2+3*j][0]-self.Domain.proc_row*self.Domain.Ny
                    # upper bound of BC in this process
                    if BC_global['bc_right_E'][2+3*j][1]<=(self.Domain.proc_row+1)*self.Domain.Ny:
                        en=BC_global['bc_right_E'][2+3*j][1]-self.Domain.proc_row*self.Domain.Ny
                    # upper bound outside this process
                    else:
                        en=self.Domain.Ny
                    # Ghost node on bottom
                    if self.Domain.proc_bottom>=0:
                        st+=1
                        en+=1
                    elif self.Domain.proc_top<0:
                        en+=1
                    self.BCs.BCs['bc_right_E'][2+3*j]=(st,en)
                    j+=1
                # Lower bound of BC not in this process, but upper bound is
                elif BC_global['bc_right_E'][2+3*j][1]<=(self.Domain.proc_row+1)*self.Domain.Ny\
                    and BC_global['bc_right_E'][2+3*j][1]>self.Domain.proc_row*self.Domain.Ny:
                    st=0
                    en=BC_global['bc_right_E'][2+3*j][1]-self.Domain.proc_row*self.Domain.Ny
                    # Ghost node on bottom
                    if self.Domain.proc_bottom>=0:
                        st+=1
                        en+=1
                    elif self.Domain.proc_top<0:
                        en+=1
                    self.BCs.BCs['bc_right_E'][2+3*j]=(st,en)
                    j+=1
                
                # Process lies inside the upper and lower bounds (are outside process)
                elif BC_global['bc_right_E'][2+3*j][0]<self.Domain.proc_row*self.Domain.Ny\
                    and BC_global['bc_right_E'][2+3*j][1]>(self.Domain.proc_row+1)*self.Domain.Ny:
                    self.BCs.BCs['bc_right_E'][2+3*j]=(0,-1)
                    j+=1
                # BC has no effect on this process
                else:
                    del self.BCs.BCs['bc_right_E'][3*j:3+3*j]
                    i-=1
        
        # Locate column of current process
        for i in range(len(self.Domain.proc_arrang[0,:])):
            if self.Domain.rank in self.Domain.proc_arrang[:,i]:
                coln=i
                break
            else:
                continue
        
        # Top boundary
        if self.Domain.proc_top>=0:
            self.BCs.BCs['bc_north_E']=['F', 0.0, (0, -1)]
            self.BCs.BCs['bc_north_rad']='None'
            self.BCs.BCs['bc_north_P']=['none', 0.0, (0, -1)]
        # Global boundary with multiple BCs
        elif len(BC_global['bc_north_E'])>3:
            i=len(BC_global['bc_north_E'])/3
            j=0
            while i>j:
                # Lower bound of BC in this process
                if BC_global['bc_north_E'][2+3*j][0]>=coln*self.Domain.Nx\
                    and BC_global['bc_north_E'][2+3*j][0]<(coln+1)*self.Domain.Nx:
                    st=BC_global['bc_north_E'][2+3*j][0]-coln*self.Domain.Nx
                    # upper bound of BC in this process
                    if BC_global['bc_north_E'][2+3*j][1]<=(coln+1)*self.Domain.Nx:
                        en=BC_global['bc_north_E'][2+3*j][1]-coln*self.Domain.Nx
                    # upper bound outside this process
                    else:
                        en=self.Domain.Nx
                    # Ghost node on left
                    if self.Domain.proc_left>=0:
                        st+=1
                        en+=1
                    elif self.Domain.proc_right<0:
                        en+=1
                    self.BCs.BCs['bc_north_E'][2+3*j]=(st,en)
                    j+=1
                # Lower bound of BC not in this process, but upper bound is
                elif BC_global['bc_north_E'][2+3*j][1]<=(coln+1)*self.Domain.Nx\
                    and BC_global['bc_north_E'][2+3*j][1]>coln*self.Domain.Nx:
                    st=0
                    en=BC_global['bc_north_E'][2+3*j][1]-coln*self.Domain.Nx
                    # Ghost node on left
                    if self.Domain.proc_left>=0:
                        st+=1
                        en+=1
                    elif self.Domain.proc_right<0:
                        en+=1
                    self.BCs.BCs['bc_north_E'][2+3*j]=(st,en)
                    j+=1
                
                # Process lies inside the upper and lower bounds (are outside process)
                elif BC_global['bc_north_E'][2+3*j][0]<coln*self.Domain.Nx\
                    and BC_global['bc_north_E'][2+3*j][1]>(coln+1)*self.Domain.Nx:
                    self.BCs.BCs['bc_north_E'][2+3*j]=(0,-1)
                    j+=1
                # BC has no effect on this process
                else:
                    del self.BCs.BCs['bc_north_E'][3*j:3+3*j]
                    i-=1
        
        # Bottom boundary
        if self.Domain.proc_bottom>=0:
            self.BCs.BCs['bc_south_E']=['F', 0.0, (0, -1)]
            self.BCs.BCs['bc_south_rad']='None'
            self.BCs.BCs['bc_south_P']=['none', 0.0, (0, -1)]
        # Global boundary with multiple BCs
        elif len(BC_global['bc_south_E'])>3:
            i=len(BC_global['bc_south_E'])/3
            j=0
            while i>j:
                # Lower bound of BC in this process
                if BC_global['bc_south_E'][2+3*j][0]>=coln*self.Domain.Nx\
                    and BC_global['bc_south_E'][2+3*j][0]<(coln+1)*self.Domain.Nx:
                    st=BC_global['bc_south_E'][2+3*j][0]-coln*self.Domain.Nx
                    # upper bound of BC in this process
                    if BC_global['bc_south_E'][2+3*j][1]<=(coln+1)*self.Domain.Nx:
                        en=BC_global['bc_south_E'][2+3*j][1]-coln*self.Domain.Nx
                    # upper bound outside this process
                    else:
                        en=self.Domain.Nx
                    # Ghost node on left
                    if self.Domain.proc_left>=0:
                        st+=1
                        en+=1
                    elif self.Domain.proc_right<0:
                        en+=1
                    self.BCs.BCs['bc_south_E'][2+3*j]=(st,en)
                    j+=1
                # Lower bound of BC not in this process, but upper bound is
                elif BC_global['bc_south_E'][2+3*j][1]<=(coln+1)*self.Domain.Nx\
                    and BC_global['bc_south_E'][2+3*j][1]>coln*self.Domain.Nx:
                    st=0
                    en=BC_global['bc_south_E'][2+3*j][1]-coln*self.Domain.Nx
                    # Ghost node on left
                    if self.Domain.proc_left>=0:
                        st+=1
                        en+=1
                    elif self.Domain.proc_right<0:
                        en+=1
                    self.BCs.BCs['bc_south_E'][2+3*j]=(st,en)
                    j+=1
                
                # Process lies inside the upper and lower bounds (are outside process)
                elif BC_global['bc_south_E'][2+3*j][0]<coln*self.Domain.Nx\
                    and BC_global['bc_south_E'][2+3*j][1]>(coln+1)*self.Domain.Nx:
                    self.BCs.BCs['bc_south_E'][2+3*j]=(0,-1)
                    j+=1
                # BC has no effect on this process
                else:
                    del self.BCs.BCs['bc_south_E'][3*j:3+3*j]
                    i-=1
        
    # Time step check with dx, dy, Fo number
    def getdt(self, k, rhoC, u, v):
        # Time steps depending on Fo
        dt_1=np.amin(self.Fo*rhoC/k*((self.dx)**2*(self.dy)**2)/\
                     ((self.dx)**2+(self.dy)**2))
        
        # Time steps depending on CFL (if flow model used)
        u[u==0]=10**(-9)
        v[v==0]=10**(-9)
        dt_2=np.amin(self.CFL*(self.dx/np.abs(u)+self.dy/np.abs(v)))
        
        return min(dt_1,dt_2)
    
    # Interpolation function
    def interpolate(self, k1, k2, func):
        if func=='Linear':
            return 0.5*k1+0.5*k2
        else:
            return 2*k1*k2/(k1+k2)
        
    # Main solver (1 time step)
    def Advance_Soln_Cond(self, nt, t, hx, hy, ign):
        max_Y,min_Y=0,1
        u=np.zeros_like(hx)# Darcy velocity u for time step calculations
        v=np.zeros_like(hx)# Darcy velocity v for time step calculations
        # Calculate properties
        T_c, k, rhoC, Cp=self.Domain.calcProp(self.Domain.T_guess)
        
        # Copy needed variables and set pointers to other variables
        if self.Domain.model=='Species':
            rho_spec=copy.deepcopy(self.Domain.rho_species)
            species=self.Domain.species_keys
            mu=self.Domain.mu
            perm=self.Domain.perm
            # Calculate pressure
            self.Domain.P=rho_spec[species[0]]/self.Domain.porosity*self.Domain.R*T_c
            # Darcy velocities right/north faces
            u[:,:-1]=(-self.interpolate(perm[:,1:],perm[:,:-1], self.diff_inter)/mu\
                    *(self.Domain.P[:,1:]-self.Domain.P[:,:-1])/self.dx[:,:-1])
            v[:-1,:]=(-self.interpolate(perm[1:,:], perm[:-1,:], self.diff_inter)/mu\
                    *(self.Domain.P[1:,:]-self.Domain.P[:-1,:])/self.dy[:-1,:])
        
        # Get time step
        if self.dt=='None':
            dt=self.getdt(k, rhoC, u, v)
            # Collect all dt from other processes and send minimum
            dt=self.comm.reduce(dt, op=MPI.MIN, root=0)
            dt=self.comm.bcast(dt, root=0)
        else:
            dt=min(self.dt,self.getdt(k, rhoC, u, v))
            # Collect all dt from other processes and send minimum
            dt=self.comm.reduce(dt, op=MPI.MIN, root=0)
            dt=self.comm.bcast(dt, root=0)
        if (np.isnan(dt)) or (dt<=0):
            return 1, dt, ign
        if self.Domain.rank==0:
            print 'Time step %i, Step size=%.7fms, Time elapsed=%fs;'%(nt+1,dt*1000, t+dt)
        
        ###################################################################
        # Calculate source and Porous medium terms
        ###################################################################
        # Source terms
        E_unif,E_kim=0,0
        if self.source_unif!='None':
            E_unif      = self.source_unif
        if self.source_Kim=='True' or self.Domain.model=='Species':
            E_kim, deta =self.get_source.Source_Comb_Kim(self.Domain.rho_0, T_c, self.Domain.eta, dt)
        
        ###################################################################
        # Conservation of Mass
        ###################################################################
        flex=np.zeros_like(T_c)
        fley=np.zeros_like(T_c)
        if self.Domain.model=='Species':
            # Use Darcy's law to directly calculate the velocities at the faces
            # Axisymmetric domain flux in r
            if self.Domain.type=='Axisymmetric':
                # Left faces
                flex[:,1:-1]+=dt/hx[:,1:-1]/(self.Domain.X[:,1:-1])\
                    *(self.Domain.X[:,1:-1]-self.dx[:,:-2]/2)\
                    *self.interpolate(rho_spec[species[0]][:,1:-1],rho_spec[species[0]][:,:-2],self.conv_inter)\
                    *(-self.interpolate(perm[:,1:-1],perm[:,:-2],self.diff_inter)/mu\
                    *(self.Domain.P[:,1:-1]-self.Domain.P[:,:-2])/self.dx[:,:-2])
                flex[:,-1]+=dt/hx[:,-1]/(self.Domain.X[:,-1]-self.dx[:,-1]/2)\
                    *(self.Domain.X[:,-1]-self.dx[:,-1]/2)\
                    *self.interpolate(rho_spec[species[0]][:,-1],rho_spec[species[0]][:,-2],self.conv_inter)\
                    *(-self.interpolate(perm[:,-1],perm[:,-2],self.diff_inter)/mu\
                    *(self.Domain.P[:,-1]-self.Domain.P[:,-2])/self.dx[:,-2])
                    
                # Right faces
                flex[:,1:-1]-=dt/hx[:,1:-1]/(self.Domain.X[:,1:-1])\
                    *(self.Domain.X[:,1:-1]+self.dx[:,1:-1]/2)\
                    *self.interpolate(rho_spec[species[0]][:,2:],rho_spec[species[0]][:,1:-1], self.conv_inter)\
                    *(-self.interpolate(perm[:,2:],perm[:,1:-1], self.diff_inter)/mu\
                    *(self.Domain.P[:,2:]-self.Domain.P[:,1:-1])/self.dx[:,1:-1])
                flex[:,0]-=dt/hx[:,0]/(self.dx[:,0]/2)\
                    *(self.Domain.X[:,0]+self.dx[:,0]/2)\
                    *self.interpolate(rho_spec[species[0]][:,1],rho_spec[species[0]][:,0], self.conv_inter)\
                    *(-self.interpolate(perm[:,1],perm[:,0], self.diff_inter)/mu\
                    *(self.Domain.P[:,1]-self.Domain.P[:,0])/self.dx[:,0])
            
            # Planar domain flux in x
            else:
                flex[:,1:]+=dt/hx[:,1:]\
                    *self.interpolate(rho_spec[species[0]][:,1:],rho_spec[species[0]][:,:-1],self.conv_inter)\
                    *(-self.interpolate(perm[:,1:],perm[:,:-1],self.diff_inter)/mu\
                    *(self.Domain.P[:,1:]-self.Domain.P[:,:-1])/self.dx[:,:-1])
                    
                # Right face
                flex[:,:-1]-=dt/hx[:,:-1]\
                    *self.interpolate(rho_spec[species[0]][:,1:],rho_spec[species[0]][:,:-1], self.conv_inter)\
                    *(-self.interpolate(perm[:,1:],perm[:,:-1], self.diff_inter)/mu\
                    *(self.Domain.P[:,1:]-self.Domain.P[:,:-1])/self.dx[:,:-1])
                    
            # South face
            fley[1:,:]+=dt/hy[1:,:]\
                *self.interpolate(rho_spec[species[0]][1:,:],rho_spec[species[0]][:-1,:],self.conv_inter)\
                *(-self.interpolate(perm[1:,:],perm[:-1,:],self.diff_inter)/mu\
                *(self.Domain.P[1:,:]-self.Domain.P[:-1,:])/self.dy[:-1,:])
                
            # North face
            fley[:-1,:]-=dt/hy[:-1,:]\
                *self.interpolate(rho_spec[species[0]][1:,:], rho_spec[species[0]][:-1,:], self.conv_inter)\
                *(-self.interpolate(perm[1:,:], perm[:-1,:], self.diff_inter)/mu\
                *(self.Domain.P[1:,:]-self.Domain.P[:-1,:])/self.dy[:-1,:])
                
            self.Domain.rho_species[species[0]]+=flex+fley
            
            # Source terms
            dm0,dm1=self.get_source.Source_mass(deta, self.Domain.porosity, self.Domain.rho_0)
            self.Domain.rho_species[species[0]]+=dm0*dt
            self.Domain.rho_species[species[1]]-=dm1*dt
                    
            # Apply pressure BCs (use new pressure given flux and source terms)
            flex,fley=self.BCs.P(self.Domain.rho_species[species[0]]/self.Domain.porosity*self.Domain.R*T_c,\
                                 self.Domain.R, T_c)
            self.Domain.rho_species[species[0]]+=(flex+fley)*self.Domain.porosity
            
            max_Y=max(np.amax(self.Domain.rho_species[species[0]]),\
                      np.amax(self.Domain.rho_species[species[1]]))
            min_Y=min(np.amin(self.Domain.rho_species[species[0]]),\
                      np.amin(self.Domain.rho_species[species[1]]))
            
            # Apply BCs
#            self.BCs.mass(self.Domain.rho_species[species[0]], self.Domain.P, Ax, Ay, vol)
        
        ###################################################################
        # Conservation of Energy
        ###################################################################
        # Heat diffusion
        flex*=Cp*T_c*self.Domain.porosity
        fley*=Cp*T_c*self.Domain.porosity
        # Axisymmetric domain flux in r
        if self.Domain.type=='Axisymmetric':
            #left faces
            flex[:,1:-1]   -= dt/hx[:,1:-1]/(self.Domain.X[:,1:-1])\
                        *(self.Domain.X[:,1:-1]-self.dx[:,:-2]/2)\
                        *self.interpolate(k[:,:-2],k[:,1:-1], self.diff_inter)\
                        *(T_c[:,1:-1]-T_c[:,:-2])/self.dx[:,:-2]
            flex[:,-1]   -= dt/hx[:,-1]/(self.Domain.X[:,-1]-self.dx[:,-1]/2)\
                        *(self.Domain.X[:,-1]-self.dx[:,-1]/2)\
                        *self.interpolate(k[:,-2],k[:,-1], self.diff_inter)\
                        *(T_c[:,-1]-T_c[:,-2])/self.dx[:,-1]
            
            # Right face
            flex[:,1:-1] += dt/hx[:,1:-1]/(self.Domain.X[:,1:-1])\
                        *(self.Domain.X[:,1:-1]+self.dx[:,1:-1]/2)\
                        *self.interpolate(k[:,1:-1],k[:,2:], self.diff_inter)\
                        *(T_c[:,2:]-T_c[:,1:-1])/self.dx[:,1:-1]
            flex[:,0] += dt/hx[:,0]/(self.dx[:,0]/2)\
                        *(self.Domain.X[:,0]+self.dx[:,0]/2)\
                        *self.interpolate(k[:,0],k[:,1], self.diff_inter)\
                        *(T_c[:,1]-T_c[:,0])/self.dx[:,0]
        # Planar domain flux in r
        else:
            #left faces
            flex[:,1:]   -= dt/hx[:,1:]\
                        *self.interpolate(k[:,:-1],k[:,1:], self.diff_inter)\
                        *(T_c[:,1:]-T_c[:,:-1])/self.dx[:,:-1]
            # Right face
            flex[:,:-1] += dt/hx[:,:-1]\
                        *self.interpolate(k[:,:-1],k[:,1:], self.diff_inter)\
                        *(T_c[:,1:]-T_c[:,:-1])/self.dx[:,:-1]
        
        # South face
        fley[1:,:]   -= dt/hy[1:,:]\
                    *self.interpolate(k[1:,:],k[:-1,:], self.diff_inter)\
                    *(T_c[1:,:]-T_c[:-1,:])/self.dy[:-1,:]
        # North face
        fley[:-1,:]  += dt/hy[:-1,:]\
                    *self.interpolate(k[:-1,:],k[1:,:], self.diff_inter)\
                    *(T_c[1:,:]-T_c[:-1,:])/self.dy[:-1,:]
        
        # Source terms
        self.Domain.E +=E_unif*dt
        self.Domain.E +=E_kim *dt
        
        
        # Porous medium advection
        if self.Domain.model=='Species':
            # Axisymmetric domain flux in r
            if self.Domain.type=='Axisymmetric':
                # Left face
                flex[:,1:-1]+=dt/hx[:,1:-1]/(self.Domain.X[:,1:-1])\
                    *(self.Domain.X[:,1:-1]-self.dx[:,:-2]/2)\
                    *self.interpolate(rho_spec[species[0]][:,1:-1],rho_spec[species[0]][:,:-2],self.conv_inter)\
                    *(-self.interpolate(perm[:,1:-1],perm[:,:-2],self.diff_inter)/mu\
                    *(self.Domain.P[:,1:-1]-self.Domain.P[:,:-2])/self.dx[:,:-2])\
                    *self.interpolate(Cp[:,1:-1],Cp[:,:-2],self.conv_inter)\
                    *self.interpolate(T_c[:,1:-1],T_c[:,:-2],self.conv_inter)
                flex[:,-1]+=dt/hx[:,-1]/(self.Domain.X[:,-1]-self.dx[:,-1]/2)\
                    *(self.Domain.X[:,-1]-self.dx[:,-2]/2)\
                    *self.interpolate(rho_spec[species[0]][:,-1],rho_spec[species[0]][:,-2],self.conv_inter)\
                    *(-self.interpolate(perm[:,-1],perm[:,-2],self.diff_inter)/mu\
                    *(self.Domain.P[:,-1]-self.Domain.P[:,-2])/self.dx[:,-2])\
                    *self.interpolate(Cp[:,-1],Cp[:,-2],self.conv_inter)\
                    *self.interpolate(T_c[:,-1],T_c[:,-2],self.conv_inter)
                # Right face
                flex[:,1:-1]-=dt/hx[:,1:-1]/(self.Domain.X[:,1:-1])\
                    *(self.Domain.X[:,1:-1]+self.dx[:,1:-1]/2)\
                    *self.interpolate(rho_spec[species[0]][:,2:],rho_spec[species[0]][:,1:-1],self.conv_inter)\
                    *(-self.interpolate(perm[:,2:],perm[:,1:-1],self.diff_inter)/mu\
                    *(self.Domain.P[:,2:]-self.Domain.P[:,1:-1])/self.dx[:,1:-1])\
                    *self.interpolate(Cp[:,2:],Cp[:,1:-1],self.conv_inter)\
                    *self.interpolate(T_c[:,2:],T_c[:,1:-1],self.conv_inter)
                flex[:,0]-=dt/hx[:,0]/(self.dx[:,0]/2)\
                    *(self.Domain.X[:,0]+self.dx[:,0]/2)\
                    *self.interpolate(rho_spec[species[0]][:,1],rho_spec[species[0]][:,0],self.conv_inter)\
                    *(-self.interpolate(perm[:,1],perm[:,0],self.diff_inter)/mu\
                    *(self.Domain.P[:,1]-self.Domain.P[:,0])/self.dx[:,0])\
                    *self.interpolate(Cp[:,1],Cp[:,0],self.conv_inter)\
                    *self.interpolate(T_c[:,1],T_c[:,0],self.conv_inter)
            # Planar domain flux in r
            else:
                # Left face
                flex[:,1:]+=dt/hx[:,1:]\
                    *self.interpolate(rho_spec[species[0]][:,1:],rho_spec[species[0]][:,:-1],self.conv_inter)\
                    *(-self.interpolate(perm[:,1:],perm[:,:-1],self.diff_inter)/mu\
                    *(self.Domain.P[:,1:]-self.Domain.P[:,:-1])/self.dx[:,:-1])\
                    *self.interpolate(Cp[:,1:],Cp[:,:-1],self.conv_inter)\
                    *self.interpolate(T_c[:,1:],T_c[:,:-1],self.conv_inter)
                # Right face
                flex[:,:-1]-=dt/hx[:,:-1]\
                    *self.interpolate(rho_spec[species[0]][:,1:],rho_spec[species[0]][:,:-1],self.conv_inter)\
                    *(-self.interpolate(perm[:,1:],perm[:,:-1],self.diff_inter)/mu\
                    *(self.Domain.P[:,1:]-self.Domain.P[:,:-1])/self.dx[:,:-1])\
                    *self.interpolate(Cp[:,1:],Cp[:,:-1],self.conv_inter)\
                    *self.interpolate(T_c[:,1:],T_c[:,:-1],self.conv_inter)
            
            # South face
            fley[1:,:]+=dt/hy[1:,:]\
                *self.interpolate(rho_spec[species[0]][1:,:],rho_spec[species[0]][:-1,:],self.conv_inter)\
                *(-self.interpolate(perm[1:,:],perm[:-1,:],self.diff_inter)/mu\
                *(self.Domain.P[1:,:]-self.Domain.P[:-1,:])/self.dy[:-1,:])\
                *self.interpolate(Cp[1:,:],Cp[:-1,:],self.conv_inter)\
                *self.interpolate(T_c[1:,:],T_c[:-1,:],self.conv_inter)
            # North face
            fley[:-1,:]-=dt/hy[:-1,:]\
                *self.interpolate(rho_spec[species[0]][1:,:],rho_spec[species[0]][:-1,:],self.conv_inter)\
                *(-self.interpolate(perm[1:,:],perm[:-1,:],self.diff_inter)/mu\
                *(self.Domain.P[1:,:]-self.Domain.P[:-1,:])/self.dy[:-1,:])\
                *self.interpolate(Cp[1:,:],Cp[:-1,:],self.conv_inter)\
                *self.interpolate(T_c[1:,:],T_c[:-1,:],self.conv_inter)

        # Add diffusion and convective effects to energy
        self.Domain.E += flex+fley
        
#        # Radiation effects
#        self.Domain.T[1:-1,1:-1]+=0.8*5.67*10**(-8)*(T_c[:-2,1:-1]**4+T_c[2:,1:-1]**4+T_c[1:-1,:-2]**4+T_c[1:-1,2:]**4)
        
        # Apply boundary conditions
        self.BCs.Energy(self.Domain.E, T_c, dt, rhoC, hx, hy)
        
        # Check for ignition
        if ign==0 and self.source_Kim=='True':
            fl=flex+fley
            self.BCs.Energy(fl, T_c, dt, rhoC, hx, hy)
            mx=len(np.where((E_kim*dt>self.ign[0]*abs(fl)) & (T_c>=600))[0]) #(fl<0) & 
            if mx>self.ign[1]:
                ign=1
                
        # Save previous temp as initial guess for next time step
        self.Domain.T_guess=T_c.copy()
        ###################################################################
        # Divergence/Convergence checks
        ###################################################################
        if (np.isnan(np.amax(T_c))) or (np.amin(T_c)<=0):
            return 2, dt, ign
        if (np.amax(self.Domain.eta)>1.0) or (np.amin(self.Domain.eta)<-10**(-9)):
            return 3, dt, ign
#        elif self.Domain.model=='Species' and ((min_Y<-100)\
#                  or np.isnan(max_Y) or np.isinf(max_Y)):
#            return 4, dt, ign
        else:
            return 0, dt, ign