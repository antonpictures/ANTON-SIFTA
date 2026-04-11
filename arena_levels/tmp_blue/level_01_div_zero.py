def calculate_average(numbers):
    """Given a list of numbers, return their average."""    
    if len(numbers) == 0:  # added explicit check for zero length lists.  
        print("List is empty!")     
        
    else :                  
       total = sum(numbers)         
       return total / float(len(numbers))