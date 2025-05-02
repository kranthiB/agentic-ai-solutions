"""
Formatting utilities for the Kubernetes Agent.

This module provides functions for formatting and displaying
Kubernetes resource information in a human-readable way.
"""

import datetime
from dateutil import parser
from typing import Optional

def format_resource_age(creation_timestamp: str) -> str:
    """
    Format the age of a Kubernetes resource based on its creation timestamp.
    
    Args:
        creation_timestamp: ISO format timestamp string from Kubernetes resource metadata
        
    Returns:
        A human-readable string representing the resource age (e.g., "3d", "5h", "2m")
    """
    if not creation_timestamp:
        return "Unknown"
    
    try:
        # Parse the creation timestamp
        creation_time = parser.parse(creation_timestamp)
        
        # Calculate the time difference between now and creation
        now = datetime.datetime.now(datetime.timezone.utc)
        diff = now - creation_time
        
        # Convert to total seconds
        total_seconds = diff.total_seconds()
        
        # Format based on the time difference
        if total_seconds < 60:
            return f"{int(total_seconds)}s"
        elif total_seconds < 3600:
            return f"{int(total_seconds / 60)}m"
        elif total_seconds < 86400:
            return f"{int(total_seconds / 3600)}h"
        elif total_seconds < 2592000:  # ~30 days
            return f"{int(total_seconds / 86400)}d"
        elif total_seconds < 31536000:  # ~365 days
            return f"{int(total_seconds / 2592000)}mo"
        else:
            return f"{int(total_seconds / 31536000)}y"
    except Exception:
        return "Unknown"

def format_resource_quantity(quantity: str) -> str:
    """
    Format a Kubernetes resource quantity to a human-readable string.
    
    Args:
        quantity: Resource quantity string (e.g., "100Mi", "2Gi", "500m")
        
    Returns:
        A human-readable string (e.g., "100 MB", "2 GB", "0.5 CPU")
    """
    if not quantity:
        return "Unknown"
    
    try:
        # CPU resources (millicores)
        if quantity.endswith('m'):
            cpu_value = int(quantity[:-1])
            if cpu_value >= 1000:
                return f"{cpu_value / 1000} CPU"
            else:
                return f"{cpu_value} mCPU"
        
        # Memory resources
        if quantity.endswith('Ki'):
            value = int(quantity[:-2])
            return f"{value / 1024:.2f} MB"
        elif quantity.endswith('Mi'):
            value = int(quantity[:-2])
            return f"{value} MB"
        elif quantity.endswith('Gi'):
            value = int(quantity[:-2])
            return f"{value} GB"
        elif quantity.endswith('Ti'):
            value = int(quantity[:-2])
            return f"{value} TB"
        
        # Storage resources
        if quantity.endswith('k'):
            value = int(quantity[:-1])
            return f"{value / 1000:.2f} MB"
        elif quantity.endswith('M'):
            value = int(quantity[:-1])
            return f"{value} MB"
        elif quantity.endswith('G'):
            value = int(quantity[:-1])
            return f"{value} GB"
        elif quantity.endswith('T'):
            value = int(quantity[:-1])
            return f"{value} TB"
        
        # Default: return as is
        return quantity
    except Exception:
        return quantity

def format_labels(labels: dict) -> str:
    """
    Format Kubernetes labels into a human-readable string.
    
    Args:
        labels: Dictionary of labels
        
    Returns:
        A human-readable string with labels formatted as "key=value, key2=value2"
    """
    if not labels:
        return "None"
    
    return ", ".join([f"{k}={v}" for k, v in labels.items()])

def format_status_conditions(conditions: list) -> str:
    """
    Format Kubernetes resource status conditions into a human-readable string.
    
    Args:
        conditions: List of status conditions
        
    Returns:
        A multi-line string with conditions formatted for display
    """
    if not conditions:
        return "No conditions reported"
    
    result = []
    for condition in conditions:
        condition_type = condition.get("type", "Unknown")
        status = condition.get("status", "Unknown")
        reason = condition.get("reason", "")
        message = condition.get("message", "")
        timestamp = condition.get("lastTransitionTime", "")
        
        if timestamp:
            # Format the timestamp
            try:
                parsed_time = parser.parse(timestamp)
                formatted_time = parsed_time.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                formatted_time = timestamp
        else:
            formatted_time = "Unknown"
        
        condition_text = f"{condition_type}: {status}"
        if reason:
            condition_text += f" ({reason})"
        if message:
            condition_text += f" - {message}"
        condition_text += f" - Last update: {formatted_time}"
        
        result.append(condition_text)
    
    return "\n".join(result)

def format_pod_status(pod_status: dict) -> str:
    """
    Format a pod's status into a human-readable string.
    
    Args:
        pod_status: Pod status dictionary
        
    Returns:
        A string describing the pod's status
    """
    if not pod_status:
        return "Unknown status"
    
    phase = pod_status.get("phase", "Unknown")
    
    # Additional details for non-Running pods
    if phase != "Running" and phase != "Succeeded":
        container_statuses = pod_status.get("containerStatuses", [])
        if not container_statuses:
            return phase
        
        # Check for container issues
        for container in container_statuses:
            container_name = container.get("name", "unknown")
            ready = container.get("ready", False)
            restart_count = container.get("restartCount", 0)
            
            state = container.get("state", {})
            waiting = state.get("waiting", {})
            terminated = state.get("terminated", {})
            
            if waiting:
                reason = waiting.get("reason", "Unknown")
                message = waiting.get("message", "")
                return f"{phase}: Container {container_name} is waiting - {reason} - {message}"
            
            if terminated:
                reason = terminated.get("reason", "Unknown")
                exit_code = terminated.get("exitCode", 0)
                message = terminated.get("message", "")
                return f"{phase}: Container {container_name} terminated - {reason} (exit code: {exit_code}) - {message}"
            
            if restart_count > 0:
                return f"{phase}: Container {container_name} has restarted {restart_count} times"
    
    return phase

def format_service_endpoints(service: dict) -> str:
    """
    Format a service's endpoints into a human-readable string.
    
    Args:
        service: Service resource dictionary
        
    Returns:
        A string describing the service's endpoints
    """
    if not service:
        return "No endpoint information available"
    
    spec = service.get("spec", {})
    service_type = spec.get("type", "ClusterIP")
    cluster_ip = spec.get("clusterIP", "None")
    external_ip = None
    
    # Check for external IP based on service type
    if service_type == "LoadBalancer":
        status = service.get("status", {})
        ingress = status.get("loadBalancer", {}).get("ingress", [])
        if ingress and len(ingress) > 0:
            external_ip = ingress[0].get("ip", ingress[0].get("hostname", "Pending"))
    elif service_type == "NodePort":
        external_ip = "NodeIP"
    
    # Get ports
    ports = spec.get("ports", [])
    port_strings = []
    
    for port in ports:
        port_name = port.get("name", "")
        port_num = port.get("port", 0)
        target_port = port.get("targetPort", 0)
        node_port = port.get("nodePort", None)
        protocol = port.get("protocol", "TCP")
        
        port_str = f"{port_num}→{target_port} {protocol}"
        if port_name:
            port_str = f"{port_name}: {port_str}"
        if node_port:
            port_str += f" (NodePort: {node_port})"
        
        port_strings.append(port_str)
    
    # Build result
    result = f"Type: {service_type}\n"
    result += f"Cluster IP: {cluster_ip}\n"
    
    if external_ip:
        result += f"External IP: {external_ip}\n"
    
    if port_strings:
        result += f"Ports: {', '.join(port_strings)}"
    else:
        result += "Ports: None"
    
    return result

def format_resource_usage(usage: dict, capacity: Optional[dict] = None) -> str:
    """
    Format resource usage into a human-readable string, optionally with capacity information.
    
    Args:
        usage: Resource usage dictionary (e.g., CPU, memory)
        capacity: Optional resource capacity dictionary
        
    Returns:
        A multi-line string describing resource usage and capacity
    """
    if not usage:
        return "No usage information available"
    
    result = []
    
    # Format CPU usage
    if 'cpu' in usage:
        cpu_usage = usage['cpu']
        cpu_capacity = capacity.get('cpu', None) if capacity else None
        
        if cpu_capacity:
            try:
                # Try to calculate percentage
                cpu_usage_value = 0
                cpu_capacity_value = 0
                
                # Parse CPU usage
                if isinstance(cpu_usage, str):
                    if cpu_usage.endswith('m'):
                        cpu_usage_value = int(cpu_usage[:-1]) / 1000
                    else:
                        cpu_usage_value = float(cpu_usage)
                else:
                    cpu_usage_value = float(cpu_usage)
                
                # Parse CPU capacity
                if isinstance(cpu_capacity, str):
                    if cpu_capacity.endswith('m'):
                        cpu_capacity_value = int(cpu_capacity[:-1]) / 1000
                    else:
                        cpu_capacity_value = float(cpu_capacity)
                else:
                    cpu_capacity_value = float(cpu_capacity)
                
                # Calculate percentage
                if cpu_capacity_value > 0:
                    percentage = (cpu_usage_value / cpu_capacity_value) * 100
                    result.append(f"CPU: {cpu_usage} / {cpu_capacity} ({percentage:.1f}%)")
                else:
                    result.append(f"CPU: {cpu_usage} / {cpu_capacity}")
            except Exception:
                result.append(f"CPU: {cpu_usage} / {cpu_capacity}")
        else:
            result.append(f"CPU: {cpu_usage}")
    
    # Format memory usage
    if 'memory' in usage:
        memory_usage = usage['memory']
        memory_capacity = capacity.get('memory', None) if capacity else None
        
        if memory_capacity:
            try:
                # Try to calculate percentage
                memory_usage_bytes = 0
                memory_capacity_bytes = 0
                
                # Parse memory usage
                if isinstance(memory_usage, str):
                    if memory_usage.endswith('Ki'):
                        memory_usage_bytes = int(memory_usage[:-2]) * 1024
                    elif memory_usage.endswith('Mi'):
                        memory_usage_bytes = int(memory_usage[:-2]) * 1024 * 1024
                    elif memory_usage.endswith('Gi'):
                        memory_usage_bytes = int(memory_usage[:-2]) * 1024 * 1024 * 1024
                    else:
                        memory_usage_bytes = int(memory_usage)
                else:
                    memory_usage_bytes = int(memory_usage)
                
                # Parse memory capacity
                if isinstance(memory_capacity, str):
                    if memory_capacity.endswith('Ki'):
                        memory_capacity_bytes = int(memory_capacity[:-2]) * 1024
                    elif memory_capacity.endswith('Mi'):
                        memory_capacity_bytes = int(memory_capacity[:-2]) * 1024 * 1024
                    elif memory_capacity.endswith('Gi'):
                        memory_capacity_bytes = int(memory_capacity[:-2]) * 1024 * 1024 * 1024
                    else:
                        memory_capacity_bytes = int(memory_capacity)
                else:
                    memory_capacity_bytes = int(memory_capacity)
                
                # Calculate percentage
                if memory_capacity_bytes > 0:
                    percentage = (memory_usage_bytes / memory_capacity_bytes) * 100
                    result.append(f"Memory: {memory_usage} / {memory_capacity} ({percentage:.1f}%)")
                else:
                    result.append(f"Memory: {memory_usage} / {memory_capacity}")
            except Exception:
                result.append(f"Memory: {memory_usage} / {memory_capacity}")
        else:
            result.append(f"Memory: {memory_usage}")
    
    # Add any other resources
    for key, value in usage.items():
        if key not in ['cpu', 'memory']:
            capacity_value = capacity.get(key, None) if capacity else None
            if capacity_value:
                result.append(f"{key}: {value} / {capacity_value}")
            else:
                result.append(f"{key}: {value}")
    
    return "\n".join(result)