#!/usr/bin/env python3
"""
Basic usage example for pygeoglim package

This script demonstrates how to use pygeoglim to extract geology attributes
for different types of geometries.
"""

from pygeoglim import load_geometry, glim_attributes, glhymps_attributes

def example_bbox():
    """Example using bounding box coordinates"""
    print("=" * 50)
    print("Example 1: Using Bounding Box")
    print("=" * 50)
    
    # Define a bounding box for Indiana region
    bbox = [-88.1, 37.8, -84.8, 41.8]
    print(f"Bounding box: {bbox}")
    
    # Load geometry
    geom = load_geometry(bbox=bbox)
    print(f"Loaded geometry with CRS: {geom.crs}")
    
    # Get GLiM attributes
    print("\nFetching GLiM lithology attributes...")
    glim_attrs = glim_attributes(geom)
    print("GLiM attributes:")
    for key, value in glim_attrs.items():
        print(f"  {key}: {value}")
    
    # Get GLHYMPS attributes
    print("\nFetching GLHYMPS hydrogeology attributes...")
    glhymps_attrs = glhymps_attributes(geom)
    print("GLHYMPS attributes:")
    for key, value in glhymps_attrs.items():
        print(f"  {key}: {value}")
    
    return {**glim_attrs, **glhymps_attrs}

def example_small_watershed():
    """Example using a smaller watershed area"""
    print("\n" + "=" * 50)
    print("Example 2: Small Watershed")
    print("=" * 50)
    
    # Smaller bounding box for faster processing
    bbox = [-85.5, 39.5, -85.0, 40.0]
    print(f"Small watershed bbox: {bbox}")
    
    geom = load_geometry(bbox=bbox)
    
    # Get combined attributes
    print("\nFetching all geology attributes...")
    glim_attrs = glim_attributes(geom)
    glhymps_attrs = glhymps_attributes(geom)
    
    # Combine results
    all_attrs = {**glim_attrs, **glhymps_attrs}
    
    print("Combined geology attributes:")
    for key, value in all_attrs.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.6f}")
        else:
            print(f"  {key}: {value}")
    
    return all_attrs

def main():
    """Run all examples"""
    print("PyGeoGLiM Package - Basic Usage Examples")
    print("========================================")
    
    try:
        # Run examples
        attrs1 = example_bbox()
        attrs2 = example_small_watershed()
        
        print("\n" + "=" * 50)
        print("Examples completed successfully!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\nError occurred: {e}")
        print("Please check your internet connection and try again.")

if __name__ == "__main__":
    main()
