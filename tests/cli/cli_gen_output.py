PET_ALL = """\
Command  All                               
add      help       Create a pet           
         operation  createPets             
         path       POST   /pets           
         function   create_pets            
delete   help       Delete a pet           
         operation  deletePetById          
         path       DELETE /pets/{petId}   
         function   delete_pet_by_id       
list     help       List all pets          
         operation  listPets               
         path       GET    /pets           
         function   list_pets              
show     help       Info for a specific pet
         operation  showPetById            
         path       GET    /pets/{petId}   
         function   show_pet_by_id         
"""
PET_HELP = """\
Command  Help                   
add      Create a pet           
delete   Delete a pet           
list     List all pets          
show     Info for a specific pet
"""
PET_FUNC = """\
Command  Function        
add      create_pets     
delete   delete_pet_by_id
list     list_pets       
show     show_pet_by_id  
"""
PET_OP = """\
Command  Operation    
add      createPets   
delete   deletePetById
list     listPets     
show     showPetById  
"""
PET_PATH = """\
Command  Path                
add      POST   /pets        
delete   DELETE /pets/{petId}
list     GET    /pets        
show     GET    /pets/{petId}
"""
P_V_ALL = """\
Command             All                                       
owners              help  Keepers of the pets                 
  create            help       Create a pet owner             
                    operation  createOwner                    
                    path       POST   /owners                 
                    function   create_owner                   
  delete            help       Delete an owner                
                    operation  deleteOwner                    
                    path       DELETE /owners/{ownerId}       
                    function   delete_owner                   
  pets              help       List owners pets               
                    operation  listOwnerPets                  
                    path       GET    /owners/{ownerId}/pets  
                    function   list_owner_pets                
  update            help       Update an owner                
                    operation  updateOwner                    
                    path       PUT    /owners/{ownerId}       
                    function   update_owner                   
pet                 help  Manage your pets                    
  create            help       Create a pet                   
                    operation  createPets                     
                    path       POST   /pets                   
                    function   create_pets                    
  delete            help       Delete a pet                   
                    operation  deletePetById                  
                    path       DELETE /pets/{petId}           
                    function   delete_pet_by_id               
  update            help       Info for a specific pet        
                    operation  showPetById                    
                    path       GET    /pets/{petId}           
                    function   show_pet_by_id                 
  examine           help  Examine your pet                    
    blood-pressure  help       Record result of blood-pressure
                    operation  checkPetBloodPressure          
                    path       POST   /examine/bloodPressure  
                    function   check_pet_blood_pressure       
    heart-rate      help       Record result of heart-rate    
                    operation  checkPetHeartRate              
                    path       POST   /examine/heartRate      
                    function   check_pet_heart_rate           
vets                help  Manage veterinarians                
  add               help       Create a veterinarian          
                    operation  createVet                      
                    path       POST   /vets                   
                    function   create_vet                     
  delete            help       Delete a veterinarian          
                    operation  deleteVet                      
                    path       DELETE /vets/{vetId}           
                    function   delete_vet                     
"""
P_V_PETS = """\
Command           Operation            
create            createPets           
delete            deletePetById        
update            showPetById          
examine                                
  blood-pressure  checkPetBloodPressure
  heart-rate      checkPetHeartRate    
"""
P_V_SHALLOW = """\
Command  Operation
owners            
pet               
vets              
"""
P_V_MID = """\
Command    Operation    
owners                  
  create   createOwner  
  delete   deleteOwner  
  pets     listOwnerPets
  update   updateOwner  
pet                     
  create   createPets   
  delete   deletePetById
  update   showPetById  
  examine               
vets                    
  add      createVet    
  delete   deleteVet    
"""
